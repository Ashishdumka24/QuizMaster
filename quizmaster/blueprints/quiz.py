"""Quiz discovery, attempt player + JSON API, results, certificates,
leaderboard and schedule calendar."""
from __future__ import annotations

import calendar as pycal
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from ..extensions import db, limiter
from ..models import DIFFICULTIES, Category, Quiz, QuizAttempt, User
from ..security import json_error, json_ok, login_required_verified, student_required
from ..services.attempts import (AttemptError, accepting_answers, eligibility, finalize_attempt, public_question,
                                 remaining_seconds, result_released, review_rows, save_answers, start_attempt,
                                 window_state)
from ..services.core import client_ip, get_bool_setting, log_action
from ..utils import clean_text, iso_utc, paginate, to_local, utcnow

bp = Blueprint("quiz", __name__)


def _visible_quiz_or_404(slug: str) -> Quiz:
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    if quiz.status not in ("published", "closed"):
        if not (current_user.is_authenticated and current_user.is_admin):
            abort(404)
    return quiz


def _own_attempt_or_404(attempt_id: int, allow_admin: bool = True) -> QuizAttempt:
    attempt = db.session.get(QuizAttempt, attempt_id)
    if attempt is None:
        abort(404)
    if attempt.user_id != current_user.id and not (allow_admin and current_user.is_admin):
        abort(404)  # do not reveal that the attempt exists
    return attempt


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@bp.route("/quizzes")
def explore():
    now = utcnow()
    q = Quiz.query.filter(Quiz.status == "published")
    search = clean_text(request.args.get("q"), 100)
    cat_slug = request.args.get("category", "")
    difficulty = request.args.get("difficulty", "")
    availability = request.args.get("availability", "")
    sort = request.args.get("sort", "newest")
    if search:
        like = f"%{search}%"
        q = q.filter((Quiz.title.ilike(like)) | (Quiz.description.ilike(like)) | (Quiz.tags.ilike(like)))
    category = Category.query.filter_by(slug=cat_slug).first() if cat_slug else None
    if category:
        q = q.filter(Quiz.category_id == category.id)
    if difficulty in DIFFICULTIES:
        q = q.filter(Quiz.difficulty == difficulty)
    if availability == "open":
        q = q.filter((Quiz.start_at.is_(None)) | (Quiz.start_at <= now)).filter(
            (Quiz.end_at.is_(None)) | (Quiz.end_at > now))
    elif availability == "upcoming":
        q = q.filter(Quiz.start_at > now)
    else:
        q = q.filter((Quiz.end_at.is_(None)) | (Quiz.end_at > now))
    if sort == "popular":
        sub = (db.session.query(QuizAttempt.quiz_id, func.count(QuizAttempt.id).label("n"))
               .group_by(QuizAttempt.quiz_id).subquery())
        q = q.outerjoin(sub, sub.c.quiz_id == Quiz.id).order_by(func.coalesce(sub.c.n, 0).desc(), Quiz.id.desc())
    elif sort == "title":
        q = q.order_by(Quiz.title.asc())
    elif sort == "shortest":
        q = q.order_by(Quiz.time_limit_minutes.asc(), Quiz.title)
    else:
        q = q.order_by(Quiz.featured.desc(), Quiz.published_at.desc().nullslast(), Quiz.id.desc())
    page = paginate(q, per_page=9)
    attempts_by_quiz = {}
    if current_user.is_authenticated and current_user.role == "student":
        rows = (db.session.query(QuizAttempt.quiz_id, func.count(QuizAttempt.id))
                .filter(QuizAttempt.user_id == current_user.id).group_by(QuizAttempt.quiz_id).all())
        attempts_by_quiz = dict(rows)
    return render_template("quiz/explore.html", page=page, categories=Category.query.order_by(Category.name).all(),
                           search=search, cat_slug=cat_slug, difficulty=difficulty, availability=availability,
                           sort=sort, window_state=window_state, attempts_by_quiz=attempts_by_quiz,
                           difficulties=DIFFICULTIES)


@bp.route("/api/quizzes/suggest")
@limiter.limit("60 per minute")
def suggest():
    """Auto-complete for the quiz search box (Q07 / Q13)."""
    term = clean_text(request.args.get("q"), 60)
    if len(term) < 2:
        return json_ok([])
    rows = (Quiz.query.filter(Quiz.status == "published", Quiz.title.ilike(f"%{term}%"))
            .order_by(Quiz.title).limit(6).all())
    return json_ok([{"title": r.title, "url": url_for("quiz.detail", slug=r.slug),
                     "category": r.category.name if r.category else "", "difficulty": r.difficulty} for r in rows])


@bp.route("/quizzes/<slug>")
def detail(slug):
    quiz = _visible_quiz_or_404(slug)
    info = eligibility(quiz, current_user) if current_user.is_authenticated else None
    my_attempts = []
    if current_user.is_authenticated:
        my_attempts = (QuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id)
                       .order_by(QuizAttempt.attempt_number.desc()).all())
    board = leaderboard_for_quiz(quiz, limit=5) if get_bool_setting("leaderboard_enabled") else []
    return render_template("quiz/detail.html", quiz=quiz, info=info, my_attempts=my_attempts, board=board,
                           state=window_state(quiz), released=result_released)


@bp.route("/quizzes/<slug>/start", methods=["POST"])
@student_required
@limiter.limit("20 per minute")
def start(slug):
    quiz = Quiz.query.filter_by(slug=slug, status="published").first_or_404()
    try:
        attempt = start_attempt(quiz, current_user, client_ip())
    except AttemptError as exc:
        flash(exc.message, "error")
        return redirect(url_for("quiz.detail", slug=slug))
    if attempt.attempt_number and (utcnow() - attempt.started_at).total_seconds() < 5:
        log_action("attempt_started", "attempt", attempt.id, f"quiz={quiz.id}", commit=True)
    return redirect(url_for("quiz.play", attempt_id=attempt.id))


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

@bp.route("/attempts/<int:attempt_id>")
@student_required
def play(attempt_id):
    attempt = _own_attempt_or_404(attempt_id, allow_admin=False)
    if attempt.status == "in_progress" and not accepting_answers(attempt):
        finalize_attempt(attempt, reason="expired")
        flash("Time ran out for this attempt. Your saved answers were submitted automatically.", "info")
    if attempt.is_finished:
        return redirect(url_for("quiz.result", attempt_id=attempt.id))
    return render_template("quiz/play.html", attempt=attempt, quiz=attempt.quiz)


def _state_payload(attempt: QuizAttempt) -> dict:
    snap = attempt.snapshot_data
    answers = {a.question_id: {"response": a.response_data, "marked": a.marked_for_review} for a in attempt.answers}
    return {
        "attempt_id": attempt.id, "status": attempt.status, "title": snap.get("quiz", {}).get("title"),
        "remaining": remaining_seconds(attempt), "deadline": iso_utc(attempt.deadline_at),
        "server_now": iso_utc(utcnow()), "negative_marking": attempt.negative_marking,
        "questions": [public_question(q) for q in snap.get("questions", [])],
        "answers": {str(k): v for k, v in answers.items()},
        "image_base": url_for("public.media", kind="questions", filename="__f__").replace("__f__", ""),
    }


@bp.route("/api/attempts/<int:attempt_id>/state")
@student_required
def api_state(attempt_id):
    attempt = _own_attempt_or_404(attempt_id, allow_admin=False)
    if attempt.status == "in_progress" and not accepting_answers(attempt):
        finalize_attempt(attempt, reason="expired")
    if attempt.is_finished:
        return json_ok({"status": attempt.status, "result_url": url_for("quiz.result", attempt_id=attempt.id)})
    return json_ok(_state_payload(attempt))


@bp.route("/api/attempts/<int:attempt_id>/answers", methods=["POST"])
@student_required
@limiter.limit("240 per minute")
def api_save(attempt_id):
    attempt = _own_attempt_or_404(attempt_id, allow_admin=False)
    payload = request.get_json(silent=True) or {}
    try:
        stored = save_answers(attempt, payload.get("answers") or [])
    except AttemptError as exc:
        extra = {"result_url": url_for("quiz.result", attempt_id=attempt.id)} if attempt.is_finished else {}
        return json_error(exc.message, exc.status, exc.code, **extra)
    return json_ok({"saved": stored, "remaining": remaining_seconds(attempt), "server_now": iso_utc(utcnow())})


@bp.route("/api/attempts/<int:attempt_id>/submit", methods=["POST"])
@student_required
@limiter.limit("30 per minute")
def api_submit(attempt_id):
    t0 = time.perf_counter()
    attempt = _own_attempt_or_404(attempt_id, allow_admin=False)
    result_url = url_for("quiz.result", attempt_id=attempt.id)
    if attempt.is_finished:  # idempotent: repeated submit returns the same result
        return json_ok({"result_url": result_url, "status": attempt.status, "duplicate": True},
                       "This attempt was already submitted.")
    payload = request.get_json(silent=True) or {}
    if accepting_answers(attempt) and payload.get("answers"):
        try:
            save_answers(attempt, payload.get("answers"))
        except AttemptError:
            pass  # deadline crossed while saving: finalise with what was stored
    was_in_progress = attempt.status == "in_progress"
    finalize_attempt(attempt, auto=bool(payload.get("auto")))
    if was_in_progress and attempt.submit_latency_ms is None:
        attempt.submit_latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        db.session.commit()
    log_action("attempt_submitted", "attempt", attempt.id,
               f"quiz={attempt.quiz_id}; score={attempt.score}/{attempt.max_score}; status={attempt.status}",
               commit=True)
    return json_ok({"result_url": result_url, "status": attempt.status}, "Quiz submitted successfully.")


# ---------------------------------------------------------------------------
# Results & certificate
# ---------------------------------------------------------------------------

@bp.route("/attempts/<int:attempt_id>/result")
@login_required_verified
def result(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    if attempt.status == "in_progress":
        if not accepting_answers(attempt):
            finalize_attempt(attempt, reason="expired")
        elif attempt.user_id == current_user.id:
            return redirect(url_for("quiz.play", attempt_id=attempt.id))
        else:
            flash("This attempt is still in progress.", "info")
            return redirect(url_for("admin.results"))
    quiz = attempt.quiz
    released = result_released(attempt) or current_user.is_admin
    rows = review_rows(attempt, include_key=released and (quiz.show_correct_answers or current_user.is_admin),
                       include_explanations=released and (quiz.show_explanations or current_user.is_admin)) \
        if released else []
    info = eligibility(quiz, current_user) if current_user.id == attempt.user_id else None
    return render_template("quiz/result.html", attempt=attempt, quiz=quiz, released=released, rows=rows, info=info)


@bp.route("/attempts/<int:attempt_id>/certificate")
@login_required_verified
def certificate(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    if not (attempt.is_finished and attempt.passed and result_released(attempt)):
        flash("A certificate is available only for passed attempts with released results.", "info")
        return redirect(url_for("quiz.result", attempt_id=attempt.id))
    return render_template("quiz/certificate.html", attempt=attempt, quiz=attempt.quiz, user=attempt.user)


# ---------------------------------------------------------------------------
# Leaderboard – ranking rule documented in docs/USER_MANUAL.md
# ---------------------------------------------------------------------------

def _visible(user: User) -> bool:
    return user.role == "student" and user.is_active_account and user.prefs.get("leaderboard_visible", True)


def leaderboard_for_quiz(quiz: Quiz, limit: int = 20) -> list[dict]:
    """Best released percentage per student; ties → less time taken → earlier submission."""
    best: dict[int, QuizAttempt] = {}
    for a in QuizAttempt.query.filter(QuizAttempt.quiz_id == quiz.id,
                                      QuizAttempt.status.in_(("submitted", "expired"))).all():
        if not result_released(a):
            continue
        cur = best.get(a.user_id)
        key = (-(a.percentage or 0), a.time_taken_seconds or 0, a.submitted_at)
        if cur is None or key < (-(cur.percentage or 0), cur.time_taken_seconds or 0, cur.submitted_at):
            best[a.user_id] = a
    rows = [a for a in best.values() if _visible(a.user)]
    rows.sort(key=lambda a: (-(a.percentage or 0), a.time_taken_seconds or 0, a.submitted_at))
    return [{"rank": i + 1, "user": a.user, "pct": a.percentage, "time": a.time_taken_seconds,
             "is_me": current_user.is_authenticated and a.user_id == current_user.id} for i, a in
            enumerate(rows[:limit])]


def leaderboard_overall(limit: int = 25) -> list[dict]:
    """Average of each student's best released percentage per quiz (min. 1 quiz);
    ties → more quizzes completed → name."""
    best = defaultdict(dict)
    for a in QuizAttempt.query.filter(QuizAttempt.status.in_(("submitted", "expired"))).all():
        if not result_released(a):
            continue
        prev = best[a.user_id].get(a.quiz_id)
        if prev is None or (a.percentage or 0) > prev:
            best[a.user_id][a.quiz_id] = a.percentage or 0
    users = {u.id: u for u in User.query.filter(User.id.in_(list(best.keys()))).all()} if best else {}
    rows = []
    for uid, quizzes in best.items():
        u = users.get(uid)
        if u and _visible(u):
            rows.append({"user": u, "avg": round(sum(quizzes.values()) / len(quizzes), 1), "quizzes": len(quizzes)})
    rows.sort(key=lambda r: (-r["avg"], -r["quizzes"], r["user"].full_name))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["is_me"] = current_user.is_authenticated and r["user"].id == current_user.id
    return rows[:limit]


@bp.route("/leaderboard")
@login_required_verified
def leaderboard():
    if not get_bool_setting("leaderboard_enabled"):
        flash("The leaderboard is currently disabled by the administrator.", "info")
        return redirect(url_for("student.dashboard") if current_user.role == "student" else url_for("admin.overview"))
    quizzes = Quiz.query.filter(Quiz.status.in_(("published", "closed"))).order_by(Quiz.title).all()
    quiz = None
    quiz_id = request.args.get("quiz", type=int)
    if quiz_id:
        quiz = next((q for q in quizzes if q.id == quiz_id), None)
    rows = leaderboard_for_quiz(quiz, limit=50) if quiz else leaderboard_overall(50)
    return render_template("quiz/leaderboard.html", quizzes=quizzes, quiz=quiz, rows=rows)


# ---------------------------------------------------------------------------
# Schedule calendar (Q03)
# ---------------------------------------------------------------------------

@bp.route("/calendar")
@login_required_verified
def calendar_view():
    today = to_local(utcnow()).date()
    try:
        month = datetime.strptime(request.args.get("month", ""), "%Y-%m").date()
    except ValueError:
        month = today.replace(day=1)
    first = month.replace(day=1)
    last_day = pycal.monthrange(first.year, first.month)[1]
    last = first.replace(day=last_day)
    events = defaultdict(list)
    statuses = ("published", "closed") if not current_user.is_admin else ("published", "closed", "draft")
    for quiz in Quiz.query.filter(Quiz.status.in_(statuses)).filter(
            (Quiz.start_at.isnot(None)) | (Quiz.end_at.isnot(None))).all():
        for kind, ts in (("opens", quiz.start_at), ("closes", quiz.end_at)):
            if ts:
                d = to_local(ts).date()
                if first <= d <= last:
                    events[d].append({"kind": kind, "quiz": quiz, "time": to_local(ts).strftime("%I:%M %p")})
    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (last + timedelta(days=1))
    upcoming = [e for d in sorted(events) if d >= today for e in events[d]][:8]
    return render_template("quiz/calendar.html", weeks=weeks, events=events, month=first, today=today,
                           prev_month=prev_month, next_month=next_month, upcoming=upcoming, date=date)
