"""Dashboard metrics. Every figure is computed from database records.

Metric definitions (also documented in docs/ADMIN_GUIDE.md):
* Verified users      – users with a confirmed email address.
* Active users (30d)  – users whose last request/login happened in the last 30 days.
* Finished attempts   – attempts with status submitted or expired.
* Average score       – mean percentage across finished attempts.
* Pass rate           – finished attempts with passed = true / finished attempts.
* Completion rate     – attempts submitted by the student before time ran out
                        (status submitted) / all finished attempts.
* Learning streak     – consecutive local calendar days (APP_TIMEZONE), ending
                        today or yesterday, with at least one finished attempt.
* Recommendations     – published, open quizzes the student has not attempted,
                        ranked by (1) categories where the student's average is
                        lowest, (2) featured flag, (3) newest first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import (Announcement, AuditLog, Category, Question, Quiz, QuizAttempt, User)
from ..utils import to_local, utcnow
from .attempts import result_released, window_state
from .core import cache

FINISHED = ("submitted", "expired")


def _ttl() -> int:
    return int(current_app.config.get("STATS_CACHE_SECONDS", 30))


def published_open_quizzes():
    now = utcnow()
    return Quiz.query.filter(Quiz.status == "published") \
        .filter((Quiz.start_at.is_(None)) | (Quiz.start_at <= now)) \
        .filter((Quiz.end_at.is_(None)) | (Quiz.end_at > now))


def student_stats(user) -> dict:
    def build():
        attempts = (QuizAttempt.query.filter(QuizAttempt.user_id == user.id, QuizAttempt.status.in_(FINISHED))
                    .order_by(QuizAttempt.submitted_at.asc()).all())
        released = [a for a in attempts if result_released(a)]
        pcts = [a.percentage or 0 for a in released]
        by_cat = defaultdict(list)
        for a in released:
            cat = a.snapshot_data.get("quiz", {}).get("category") or "General"
            by_cat[cat].append(a.percentage or 0)
        subject = sorted(({"name": k, "avg": round(sum(v) / len(v), 1), "count": len(v)} for k, v in by_cat.items()),
                         key=lambda x: -x["count"])
        days = sorted({to_local(a.submitted_at).date() for a in attempts if a.submitted_at}, reverse=True)
        streak = 0
        today = to_local(utcnow()).date()
        if days and (today - days[0]).days <= 1:
            streak = 1
            for prev, cur in zip(days, days[1:]):
                if (prev - cur).days == 1:
                    streak += 1
                else:
                    break
        attempted_ids = {a.quiz_id for a in attempts}
        total_published = Quiz.query.filter_by(status="published").count()
        completed_published = Quiz.query.filter(Quiz.status == "published", Quiz.id.in_(attempted_ids)).count() \
            if attempted_ids else 0
        return {
            "total_attempts": len(attempts),
            "released_count": len(released),
            "avg_score": round(sum(pcts) / len(pcts), 1) if pcts else None,
            "best_score": round(max(pcts), 1) if pcts else None,
            "passed": sum(1 for a in released if a.passed),
            "pass_rate": round(sum(1 for a in released if a.passed) / len(released) * 100, 1) if released else None,
            "trend": [{"label": to_local(a.submitted_at).strftime("%d %b"), "value": round(a.percentage or 0, 1),
                       "title": a.quiz.title if a.quiz else ""} for a in released[-12:]],
            "subjects": subject,
            "streak": streak,
            "completion": {"done": completed_published, "total": total_published,
                           "pct": round(completed_published / total_published * 100) if total_published else 0},
            "time_spent": sum(a.time_taken_seconds or 0 for a in attempts),
            "weak_categories": [s["name"] for s in sorted(subject, key=lambda s: s["avg"])],
            "attempted_ids": attempted_ids,
        }

    return cache.get_or_set(f"student:{user.id}:stats", _ttl(), build)


def recommendations(user, limit: int = 4) -> list:
    stats = student_stats(user)
    attempted = stats["attempted_ids"]
    weak = stats["weak_categories"]
    candidates = [q for q in published_open_quizzes().all() if q.id not in attempted and q.question_count > 0]

    def rank(q):
        cat = q.category.name if q.category else "General"
        weak_rank = weak.index(cat) if cat in weak else len(weak) + 1
        return (weak_rank, 0 if q.featured else 1, -(q.published_at or q.created_at).timestamp())

    return sorted(candidates, key=rank)[:limit]


def announcements_for(user, limit: int = 5):
    aud = ["all", "admins" if user.role == "admin" else "students"]
    return (Announcement.query.filter(Announcement.is_published.is_(True), Announcement.audience.in_(aud))
            .order_by(Announcement.pinned.desc(), Announcement.published_at.desc()).limit(limit).all())


def admin_overview() -> dict:
    def build():
        now = utcnow()
        users = db.session.query(
            func.count(User.id),
            func.sum(db.case((User.role == "student", 1), else_=0)),
            func.sum(db.case((User.role == "admin", 1), else_=0)),
            func.sum(db.case((User.email_verified_at.isnot(None), 1), else_=0)),
            func.sum(db.case((User.last_seen_at >= now - timedelta(days=30), 1), else_=0)),
            func.sum(db.case((User.created_at >= now - timedelta(days=7), 1), else_=0)),
            func.sum(db.case((User.is_active_account.is_(False), 1), else_=0)),
        ).one()
        quizzes = dict(db.session.query(Quiz.status, func.count(Quiz.id)).group_by(Quiz.status).all())
        att = db.session.query(
            func.count(QuizAttempt.id),
            func.avg(QuizAttempt.percentage),
            func.sum(db.case((QuizAttempt.passed.is_(True), 1), else_=0)),
            func.sum(db.case((QuizAttempt.status == "submitted", 1), else_=0)),
            func.avg(QuizAttempt.submit_latency_ms),
        ).filter(QuizAttempt.status.in_(FINISHED)).one()
        in_progress = QuizAttempt.query.filter_by(status="in_progress").count()
        finished = att[0] or 0
        qtypes = dict(db.session.query(Question.qtype, func.count(Question.id))
                      .filter(Question.is_archived.is_(False)).group_by(Question.qtype).all())
        qdiff = dict(db.session.query(Question.difficulty, func.count(Question.id))
                     .filter(Question.is_archived.is_(False)).group_by(Question.difficulty).all())
        archived_q = Question.query.filter_by(is_archived=True).count()

        # attempts per day (last 14 local days)
        since = now - timedelta(days=14)
        per_day = defaultdict(int)
        for (ts,) in db.session.query(QuizAttempt.submitted_at).filter(
                QuizAttempt.status.in_(FINISHED), QuizAttempt.submitted_at >= since).all():
            per_day[to_local(ts).date()] += 1
        today = to_local(now).date()
        series = [{"label": (today - timedelta(days=i)).strftime("%d %b"),
                   "value": per_day.get(today - timedelta(days=i), 0)} for i in range(13, -1, -1)]

        bins = [0] * 10
        for (p,) in db.session.query(QuizAttempt.percentage).filter(QuizAttempt.status.in_(FINISHED)).all():
            bins[min(9, int((p or 0) // 10))] += 1
        histogram = [{"label": f"{i * 10}-{i * 10 + 10 if i < 9 else 100}", "value": v} for i, v in enumerate(bins)]

        cat_perf = []
        rows = (db.session.query(Category.name, Category.color, func.avg(QuizAttempt.percentage),
                                 func.count(QuizAttempt.id))
                .join(Quiz, Quiz.category_id == Category.id)
                .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
                .filter(QuizAttempt.status.in_(FINISHED)).group_by(Category.id).all())
        for name, color, avg, cnt in rows:
            cat_perf.append({"label": name, "value": round(avg or 0, 1), "count": cnt, "color": color})

        top_quizzes = (db.session.query(Quiz.title, func.count(QuizAttempt.id), func.avg(QuizAttempt.percentage))
                       .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
                       .filter(QuizAttempt.status.in_(FINISHED))
                       .group_by(Quiz.id).order_by(func.count(QuizAttempt.id).desc()).limit(5).all())

        return {
            "users_total": users[0] or 0, "students": users[1] or 0, "admins": users[2] or 0,
            "verified": users[3] or 0, "active_30d": users[4] or 0, "new_7d": users[5] or 0,
            "disabled": users[6] or 0,
            "quizzes_total": sum(quizzes.values()), "quizzes_published": quizzes.get("published", 0),
            "quizzes_draft": quizzes.get("draft", 0), "quizzes_closed": quizzes.get("closed", 0),
            "quizzes_archived": quizzes.get("archived", 0),
            "attempts_finished": finished, "attempts_in_progress": in_progress,
            "avg_score": round(att[1], 1) if att[1] is not None else None,
            "pass_rate": round((att[2] or 0) / finished * 100, 1) if finished else None,
            "completion_rate": round((att[3] or 0) / finished * 100, 1) if finished else None,
            "avg_submit_ms": round(att[4], 1) if att[4] is not None else None,
            "questions_active": sum(qtypes.values()), "questions_archived": archived_q,
            "qtypes": qtypes, "qdiff": qdiff,
            "attempts_series": series, "histogram": histogram, "category_perf": cat_perf,
            "top_quizzes": [{"title": t, "attempts": c, "avg": round(a or 0, 1)} for t, c, a in top_quizzes],
        }

    return cache.get_or_set("admin:overview", _ttl(), build)


def recent_activity(limit: int = 8):
    return AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()


def recent_registrations(limit: int = 6):
    return User.query.order_by(User.created_at.desc()).limit(limit).all()


def quiz_item_analysis(quiz_id: int) -> list[dict]:
    """Per-question facility index (% correct) from frozen snapshots."""
    stats = defaultdict(lambda: {"text": "", "correct": 0, "answered": 0, "seen": 0})
    for a in QuizAttempt.query.filter(QuizAttempt.quiz_id == quiz_id, QuizAttempt.status.in_(FINISHED)).all():
        ans = {x.question_id: x for x in a.answers}
        for q in a.snapshot_data.get("questions", []):
            s = stats[q["id"]]
            s["text"] = q["text"]
            s["seen"] += 1
            row = ans.get(q["id"])
            if row and row.response:
                s["answered"] += 1
                if row.is_correct:
                    s["correct"] += 1
    out = []
    for qid, s in stats.items():
        facility = round(s["correct"] / s["seen"] * 100, 1) if s["seen"] else 0
        out.append({"id": qid, "text": s["text"], "seen": s["seen"], "answered": s["answered"],
                    "correct": s["correct"], "facility": facility,
                    "band": "Easy" if facility >= 75 else "Moderate" if facility >= 40 else "Difficult"})
    return sorted(out, key=lambda r: r["facility"])


def quiz_card_meta(quiz: Quiz) -> dict:
    return {"state": window_state(quiz), "questions": quiz.question_count, "marks": quiz.total_marks}
