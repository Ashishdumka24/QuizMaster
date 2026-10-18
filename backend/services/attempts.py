"""Quiz attempt lifecycle: eligibility -> start (snapshot) -> autosave -> finalise.

Attempt states
--------------
in_progress : started, deadline not yet passed (+ grace period).
submitted   : finalised by the student (manual submit or client-side timer).
expired     : the server found the attempt past its deadline and finalised it
              using the answers saved before the deadline.

The deadline is fixed on the server when the attempt starts. Answers arriving
after ``deadline + SUBMISSION_GRACE_SECONDS`` are rejected, so editing the
browser clock or JavaScript cannot buy extra time.
"""
from __future__ import annotations

import json
import random
import time
from datetime import timedelta

from flask import current_app, url_for
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import AttemptAnswer, Quiz, QuizAttempt
from ..utils import utcnow
from .core import cache, notify
from .grading import CHOICE_TYPES, grade_attempt, sanitize_response


class AttemptError(Exception):
    def __init__(self, message: str, code: str = "attempt_error", status: int = 400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _grace() -> timedelta:
    return timedelta(seconds=current_app.config.get("SUBMISSION_GRACE_SECONDS", 10))


def window_state(quiz: Quiz, now=None) -> str:
    now = now or utcnow()
    if quiz.start_at and now < quiz.start_at:
        return "upcoming"
    if quiz.end_at and now >= quiz.end_at:
        return "ended"
    return "open"


def eligibility(quiz: Quiz, user) -> dict:
    now = utcnow()
    finalize_overdue(user_id=user.id, quiz_id=quiz.id)
    attempts = QuizAttempt.query.filter_by(user_id=user.id, quiz_id=quiz.id)
    used = attempts.count()
    in_progress = attempts.filter_by(status="in_progress").first()
    left = None if quiz.max_attempts == 0 else max(0, quiz.max_attempts - used)
    info = {"can_start": False, "can_resume": bool(in_progress), "in_progress": in_progress,
            "attempts_used": used, "attempts_left": left, "reason": None, "state": window_state(quiz, now)}
    if in_progress:
        info["reason"] = "You have an attempt in progress. Resume it to continue."
        return info
    if user.role != "student":
        info["reason"] = "Only student accounts can attempt quizzes. Use Preview to review this quiz."
    elif quiz.status != "published":
        info["reason"] = "This quiz is not currently available."
    elif info["state"] == "upcoming":
        info["reason"] = "This quiz has not opened yet."
    elif info["state"] == "ended":
        info["reason"] = "This quiz has closed."
    elif quiz.question_count == 0:
        info["reason"] = "This quiz has no questions yet."
    elif left == 0:
        info["reason"] = "You have used all permitted attempts for this quiz."
    else:
        info["can_start"] = True
    return info


def build_snapshot(quiz: Quiz) -> dict:
    rng = random.SystemRandom()
    questions = []
    for q in quiz.active_questions:
        options = [{"id": o.id, "text": o.text} for o in q.options]
        if quiz.shuffle_options and q.qtype in ("single", "multiple"):
            rng.shuffle(options)
        questions.append({
            "id": q.id, "type": q.qtype, "text": q.text, "image": q.image_filename,
            "marks": float(q.marks), "negative": float(q.negative_marks or 0),
            "explanation": q.explanation or "", "topic": q.topic or "", "difficulty": q.difficulty,
            "category": q.category.name if q.category else "",
            "options": options if q.qtype in CHOICE_TYPES else [],
            "correct": sorted(o.id for o in q.options if o.is_correct) if q.qtype in CHOICE_TYPES else [],
            "accepted": q.answers_list if q.qtype not in CHOICE_TYPES else [],
        })
    if quiz.shuffle_questions:
        rng.shuffle(questions)
    return {
        "quiz": {"id": quiz.id, "title": quiz.title, "time_limit": quiz.time_limit_minutes,
                 "category": quiz.category.name if quiz.category else ""},
        "questions": questions,
    }


def start_attempt(quiz: Quiz, user, ip: str | None = None) -> QuizAttempt:
    info = eligibility(quiz, user)
    if info["in_progress"]:
        return info["in_progress"]
    if not info["can_start"]:
        raise AttemptError(info["reason"] or "You cannot start this quiz.", "not_eligible", 403)

    now = utcnow()
    deadline = now + timedelta(minutes=quiz.time_limit_minutes)
    if quiz.end_at and quiz.end_at < deadline:
        deadline = quiz.end_at
    number = (db.session.query(func.max(QuizAttempt.attempt_number))
              .filter_by(user_id=user.id, quiz_id=quiz.id).scalar() or 0) + 1
    snap = build_snapshot(quiz)
    attempt = QuizAttempt(
        user_id=user.id, quiz_id=quiz.id, attempt_number=number, status="in_progress",
        started_at=now, deadline_at=deadline, pass_percentage=quiz.pass_percentage,
        negative_marking=quiz.negative_marking, snapshot=json.dumps(snap),
        max_score=round(sum(q["marks"] for q in snap["questions"]), 2), client_ip=ip,
    )
    db.session.add(attempt)
    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent request (double click) created the same attempt number.
        db.session.rollback()
        existing = QuizAttempt.query.filter_by(user_id=user.id, quiz_id=quiz.id, status="in_progress").first()
        if existing:
            return existing
        raise AttemptError("Could not start the attempt. Please try again.", "conflict", 409)
    cache.clear("admin:")
    return attempt


def remaining_seconds(attempt: QuizAttempt) -> int:
    return max(0, int((attempt.deadline_at - utcnow()).total_seconds()))


def accepting_answers(attempt: QuizAttempt) -> bool:
    return attempt.status == "in_progress" and utcnow() <= attempt.deadline_at + _grace()


def save_answers(attempt: QuizAttempt, items: list) -> int:
    """Upsert answers. Returns the number of answers stored."""
    if attempt.status != "in_progress":
        raise AttemptError("This attempt has already been submitted.", "closed", 409)
    if not accepting_answers(attempt):
        finalize_attempt(attempt, reason="expired")
        raise AttemptError("Time is up. Your saved answers have been submitted.", "expired", 409)
    if not isinstance(items, list) or len(items) > 500:
        raise AttemptError("Invalid answer payload.", "invalid", 400)

    questions = {q["id"]: q for q in attempt.snapshot_data.get("questions", [])}
    existing = {a.question_id: a for a in attempt.answers}
    stored = 0
    now = utcnow()
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            qid = int(item.get("question_id"))
        except (TypeError, ValueError):
            continue
        q = questions.get(qid)
        if q is None:
            continue
        response = sanitize_response(q, item.get("response"))
        row = existing.get(qid)
        if row is None:
            row = AttemptAnswer(attempt_id=attempt.id, question_id=qid)
            db.session.add(row)
            existing[qid] = row
        row.response = json.dumps(response) if response is not None else None
        if "marked" in item:
            row.marked_for_review = bool(item.get("marked"))
        row.answered_at = now
        stored += 1
    db.session.commit()
    return stored


def finalize_attempt(attempt: QuizAttempt, reason: str = "submitted", auto: bool = False) -> QuizAttempt:
    """Idempotently finalise and grade an attempt.

    A compare-and-set UPDATE (status must still be in_progress) guarantees that
    concurrent or repeated submissions grade the attempt exactly once.
    """
    now = utcnow()
    past_deadline = now > attempt.deadline_at + _grace()
    new_status = "expired" if (reason == "expired" or past_deadline) else "submitted"
    finished_at = min(now, attempt.deadline_at) if new_status == "expired" else min(now, attempt.deadline_at + _grace())
    result = db.session.execute(
        update(QuizAttempt)
        .where(QuizAttempt.id == attempt.id, QuizAttempt.status == "in_progress")
        .values(status=new_status, submitted_at=finished_at)
    )
    if result.rowcount == 0:
        db.session.rollback()
        db.session.refresh(attempt)
        return attempt
    db.session.refresh(attempt)
    t0 = time.perf_counter()
    grade_attempt(attempt)
    attempt.grading_ms = round((time.perf_counter() - t0) * 1000, 3)
    attempt.auto_submitted = bool(auto or new_status == "expired")
    attempt.time_taken_seconds = max(0, int((finished_at - attempt.started_at).total_seconds()))
    quiz = attempt.quiz
    if result_released(attempt):
        notify(attempt.user_id, f"Result ready: {quiz.title}",
               f"You scored {attempt.percentage:.1f}% ({'Passed' if attempt.passed else 'Not passed'}).",
               url_for("quiz.result", attempt_id=attempt.id) if _has_request() else None, "success")
    else:
        notify(attempt.user_id, f"Submitted: {quiz.title}",
               "Your answers were recorded. Results will be released by your instructor.", None, "info")
    db.session.commit()
    cache.clear("admin:")
    cache.clear(f"student:{attempt.user_id}")
    return attempt


def _has_request() -> bool:
    from flask import has_request_context
    return has_request_context()


def finalize_overdue(user_id: int | None = None, quiz_id: int | None = None) -> int:
    cutoff = utcnow() - _grace()
    q = QuizAttempt.query.filter(QuizAttempt.status == "in_progress", QuizAttempt.deadline_at < cutoff)
    if user_id:
        q = q.filter(QuizAttempt.user_id == user_id)
    if quiz_id:
        q = q.filter(QuizAttempt.quiz_id == quiz_id)
    count = 0
    for attempt in q.limit(200).all():
        finalize_attempt(attempt, reason="expired")
        count += 1
    return count


def result_released(attempt: QuizAttempt) -> bool:
    quiz = attempt.quiz
    if not attempt.is_finished or quiz is None:
        return False
    if quiz.result_release == "immediate":
        return True
    if quiz.result_release == "after_close":
        return quiz.status in ("closed", "archived") or bool(quiz.end_at and utcnow() >= quiz.end_at) \
            or quiz.results_published
    return bool(quiz.results_published)


def public_question(q: dict) -> dict:
    """Question payload for the quiz player – never includes the answer key."""
    return {"id": q["id"], "type": q["type"], "text": q["text"], "marks": q["marks"],
            "negative": q["negative"], "image": q.get("image"),
            "options": [{"id": o["id"], "text": o["text"]} for o in q.get("options", [])]}


def review_rows(attempt: QuizAttempt, include_key: bool, include_explanations: bool) -> list[dict]:
    answers = {a.question_id: a for a in attempt.answers}
    rows = []
    for i, q in enumerate(attempt.snapshot_data.get("questions", []), start=1):
        ans = answers.get(q["id"])
        resp = ans.response_data if ans else None
        selected = set((resp or {}).get("options") or [])
        row = {
            "n": i, "q": q, "response": resp, "selected": selected,
            "text_answer": (resp or {}).get("text"),
            "is_correct": ans.is_correct if ans else None,
            "marks": ans.marks_awarded if ans and ans.marks_awarded is not None else 0.0,
            "answered": bool(resp), "override": bool(ans and ans.manual_override),
            "note": ans.override_note if ans else None, "answer_id": ans.id if ans else None,
            "correct_ids": set(q.get("correct") or []) if include_key else set(),
            "accepted": q.get("accepted") if include_key else [],
            "explanation": q.get("explanation") if include_explanations else "",
        }
        rows.append(row)
    return rows
