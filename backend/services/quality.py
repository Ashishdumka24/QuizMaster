"""TQM / Statistical Quality Control analytics computed from live records.

Tools (BBAT104 guideline §6.3): Pareto (80/20), Ishikawa (fishbone), check sheet
& defect log, FMEA (RPN = S x O x D). Additional process data: I-MR control
chart of submission latency (CTQ for the Online Quiz System: "zero latency
during submissions & auto-grading"), score histogram and customer satisfaction.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from sqlalchemy import func

from ..extensions import db
from ..models import (DEFECT_STATUSES, DEFECT_TYPES, FISHBONE_CATEGORIES, SEVERITIES, Defect, FMEAItem, Feedback,
                      PDCAAction, Question, QuizAttempt, RequestMetric)
from .grading import grade_question

CTQ_TARGETS = {
    "submit_latency_ms": 500.0,   # p95 server processing time for a final submission
    "autosave_latency_ms": 300.0,  # p95 for answer autosave calls
    "autosave_success_pct": 99.0,
    "grading_accuracy_pct": 100.0,
    "csat_pct": 80.0,
}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    k = (len(vals) - 1) * pct / 100
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[f] + (vals[c] - vals[f]) * (k - f), 2)


def pareto_data() -> dict:
    rows = (db.session.query(Defect.defect_type, func.sum(Defect.occurrences))
            .group_by(Defect.defect_type).all())
    items = sorted(((t, int(c or 0)) for t, c in rows), key=lambda x: -x[1])
    total = sum(c for _, c in items)
    cum = 0
    out = []
    for label, count in items:
        prev_cum_pct = cum / total * 100 if total else 0
        cum += count
        cum_pct = round(cum / total * 100, 1) if total else 0
        out.append({"label": label, "count": count, "pct": round(count / total * 100, 1) if total else 0,
                    "cum_pct": cum_pct, "vital": prev_cum_pct < 80})
    return {"items": out, "total": total,
            "vital_few": [i["label"] for i in out if i["vital"]]}


def fishbone_data() -> dict:
    groups = {c: [] for c in FISHBONE_CATEGORIES}
    for d in Defect.query.order_by(Defect.occurrences.desc(), Defect.detected_at.desc()).all():
        cause = (d.root_cause or d.title or "").strip()
        if cause:
            groups.setdefault(d.fishbone_category, []).append({"code": d.code, "cause": cause[:90],
                                                              "type": d.defect_type, "severity": d.severity})
    return {"effect": "Defects in quiz submission & auto-grading quality", "groups": groups}


def checksheet() -> dict:
    """Defect type x severity tally plus status counts (standardised check sheet)."""
    matrix = defaultdict(lambda: Counter())
    status = defaultdict(lambda: Counter())
    for d in Defect.query.all():
        matrix[d.defect_type][d.severity] += d.occurrences
        status[d.defect_type][d.status] += 1
    rows = []
    for t in DEFECT_TYPES:
        if t in matrix:
            rows.append({"type": t, "sev": {s: matrix[t].get(s, 0) for s in SEVERITIES},
                         "total": sum(matrix[t].values()),
                         "status": {s: status[t].get(s, 0) for s in DEFECT_STATUSES}})
    totals = {s: sum(r["sev"][s] for r in rows) for s in SEVERITIES}
    return {"rows": rows, "severities": SEVERITIES, "statuses": DEFECT_STATUSES, "totals": totals,
            "grand_total": sum(totals.values())}


def control_chart(limit: int = 60) -> dict:
    """Individuals & moving-range (I-MR) chart of submission processing time."""
    vals = [round(v, 2) for (v,) in db.session.query(QuizAttempt.submit_latency_ms)
            .filter(QuizAttempt.submit_latency_ms.isnot(None))
            .order_by(QuizAttempt.submitted_at.desc()).limit(limit).all()][::-1]
    out = {"values": vals, "n": len(vals), "enough": len(vals) >= 10}
    if len(vals) >= 2:
        mean = statistics.fmean(vals)
        mrs = [abs(b - a) for a, b in zip(vals, vals[1:])]
        mr_bar = statistics.fmean(mrs)
        ucl = mean + 2.66 * mr_bar
        lcl = max(0.0, mean - 2.66 * mr_bar)
        out.update({"mean": round(mean, 2), "mr_bar": round(mr_bar, 2), "ucl": round(ucl, 2), "lcl": round(lcl, 2),
                    "out_of_control": [i for i, v in enumerate(vals) if v > ucl or v < lcl]})
    return out


def ctq_metrics() -> dict:
    submit = [v for (v,) in db.session.query(QuizAttempt.submit_latency_ms)
              .filter(QuizAttempt.submit_latency_ms.isnot(None)).all()]
    grading = [v for (v,) in db.session.query(QuizAttempt.grading_ms).filter(QuizAttempt.grading_ms.isnot(None)).all()]
    saves = db.session.query(RequestMetric.duration_ms, RequestMetric.status_code) \
        .filter(RequestMetric.endpoint == "quiz.api_save").all()
    save_ms = [d for d, _ in saves]
    save_ok = sum(1 for _, s in saves if 200 <= s < 300)
    expired_reject = sum(1 for _, s in saves if s == 409)
    q_total = Question.query.filter_by(is_archived=False).count()
    q_auto = Question.query.filter(Question.is_archived.is_(False),
                                   Question.qtype.in_(["single", "multiple", "truefalse", "short", "fill"])).count()
    fb = [r for (r,) in db.session.query(Feedback.rating).all()]
    return {
        "submit": {"n": len(submit), "avg": round(statistics.fmean(submit), 2) if submit else None,
                   "p95": percentile(submit, 95), "max": round(max(submit), 2) if submit else None,
                   "target": CTQ_TARGETS["submit_latency_ms"]},
        "grading": {"n": len(grading), "avg": round(statistics.fmean(grading), 3) if grading else None,
                    "p95": percentile(grading, 95)},
        "autosave": {"n": len(saves), "avg": round(statistics.fmean(save_ms), 2) if save_ms else None,
                     "p95": percentile(save_ms, 95), "target": CTQ_TARGETS["autosave_latency_ms"],
                     "success_pct": round(save_ok / (len(saves) - expired_reject) * 100, 2)
                     if len(saves) - expired_reject > 0 else None,
                     "expired_rejections": expired_reject},
        "auto_grade_coverage": round(q_auto / q_total * 100, 1) if q_total else None,
        "feedback": {"n": len(fb), "avg": round(statistics.fmean(fb), 2) if fb else None,
                     "csat": round(sum(1 for r in fb if r >= 4) / len(fb) * 100, 1) if fb else None,
                     "dist": {i: fb.count(i) for i in range(1, 6)}},
        "targets": CTQ_TARGETS,
    }


def grading_reproducibility(limit: int = 200) -> dict:
    """QC check: independently re-grade finished attempts from their frozen
    snapshot and compare with the stored marks (manual overrides excluded)."""
    checked = mismatched = 0
    bad = []
    for a in (QuizAttempt.query.filter(QuizAttempt.status.in_(("submitted", "expired")),
                                       QuizAttempt.manually_adjusted.is_(False))
              .order_by(QuizAttempt.id.desc()).limit(limit).all()):
        answers = {x.question_id: x for x in a.answers}
        total = 0.0
        for q in a.snapshot_data.get("questions", []):
            row = answers.get(q["id"])
            _, _, marks = grade_question(q, row.response_data if row else None, a.negative_marking)
            total += marks
        expected = round(max(0.0, total), 2)
        checked += 1
        if a.score is None or abs(expected - a.score) > 0.001:
            mismatched += 1
            bad.append(a.id)
    return {"checked": checked, "mismatched": mismatched, "mismatched_ids": bad[:20],
            "accuracy": round((checked - mismatched) / checked * 100, 2) if checked else None}


def defect_summary() -> dict:
    by_status = dict(db.session.query(Defect.status, func.count(Defect.id)).group_by(Defect.status).all())
    by_sev = dict(db.session.query(Defect.severity, func.count(Defect.id)).group_by(Defect.severity).all())
    total = sum(by_status.values())
    closed = sum(by_status.get(s, 0) for s in ("Resolved", "Verified", "Closed"))
    return {"total": total, "by_status": by_status, "by_severity": by_sev,
            "open": total - closed, "closure_rate": round(closed / total * 100, 1) if total else None}


def fmea_summary() -> dict:
    items = FMEAItem.query.all()
    rpns = sorted((i.rpn for i in items), reverse=True)
    improved = [i for i in items if i.new_rpn is not None]
    return {"count": len(items), "max_rpn": rpns[0] if rpns else None,
            "high": sum(1 for r in rpns if r >= 120), "avg_rpn": round(statistics.fmean(rpns), 1) if rpns else None,
            "risk_reduction": round((1 - sum(i.new_rpn for i in improved) / sum(i.rpn for i in improved)) * 100, 1)
            if improved else None}


def pdca_summary() -> dict:
    return dict(db.session.query(PDCAAction.stage, func.count(PDCAAction.id)).group_by(PDCAAction.stage).all())
