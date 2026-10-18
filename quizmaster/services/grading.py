"""Authoritative, server-side auto-grading.

Rules (documented in docs/SRS.md §5.4):
* single / true-false : correct option -> full marks.
* multiple select     : the selected set must exactly equal the correct set
                        (all-or-nothing, no partial credit).
* short / fill blank  : case-, whitespace- and trailing-punctuation-insensitive
                        exact match against any accepted answer. This is NOT
                        semantic grading; administrators can override marks
                        manually from Results & Attempts.
* wrong answer        : -negative_marks when the quiz has negative marking on.
* unanswered          : 0 marks.
* attempt total       : floored at 0; percentage = score / max_score * 100.
"""
from __future__ import annotations

from ..utils import normalize_answer

CHOICE_TYPES = ("single", "multiple", "truefalse")


def is_answered(question: dict, response) -> bool:
    if not response:
        return False
    if question["type"] in CHOICE_TYPES:
        return bool(isinstance(response, dict) and response.get("options"))
    return bool(isinstance(response, dict) and str(response.get("text", "")).strip())


def sanitize_response(question: dict, raw):
    """Coerce client input into a canonical response or None (unanswered)."""
    if raw is None:
        return None
    if question["type"] in CHOICE_TYPES:
        values = raw.get("options") if isinstance(raw, dict) else raw
        if not isinstance(values, (list, tuple)):
            values = [values]
        valid = {o["id"] for o in question["options"]}
        picked = []
        for v in values:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if iv in valid and iv not in picked:
                picked.append(iv)
        if question["type"] in ("single", "truefalse"):
            picked = picked[:1]
        return {"options": sorted(picked)} if picked else None
    text = raw.get("text") if isinstance(raw, dict) else raw
    text = str(text or "").replace("\x00", "").strip()[:500]
    return {"text": text} if text else None


def grade_question(question: dict, response, negative_marking: bool) -> tuple[str, bool | None, float]:
    """Return (outcome, is_correct, marks) where outcome is correct|incorrect|unanswered."""
    if not is_answered(question, response):
        return "unanswered", None, 0.0
    if question["type"] in CHOICE_TYPES:
        correct = set(question.get("correct") or [])
        ok = set(response.get("options") or []) == correct and bool(correct)
    else:
        accepted = {normalize_answer(a) for a in (question.get("accepted") or [])}
        ok = normalize_answer(response.get("text")) in accepted
    if ok:
        return "correct", True, float(question["marks"])
    penalty = float(question.get("negative") or 0) if negative_marking else 0.0
    return "incorrect", False, -penalty


def grade_attempt(attempt) -> None:
    """(Re)compute every answer and the attempt totals from the frozen snapshot."""
    snap = attempt.snapshot_data
    answers = {a.question_id: a for a in attempt.answers}
    total = max_total = 0.0
    correct = incorrect = unanswered = 0
    for q in snap.get("questions", []):
        max_total += float(q["marks"])
        ans = answers.get(q["id"])
        response = ans.response_data if ans else None
        outcome, is_correct, marks = grade_question(q, response, attempt.negative_marking)
        if ans is not None:
            if ans.manual_override and ans.marks_awarded is not None:
                marks = float(ans.marks_awarded)
                is_correct = ans.is_correct
                outcome = "correct" if is_correct else ("incorrect" if is_answered(q, response) else "unanswered")
            else:
                ans.is_correct = is_correct
                ans.marks_awarded = marks
        total += marks
        if outcome == "correct":
            correct += 1
        elif outcome == "incorrect":
            incorrect += 1
        else:
            unanswered += 1
    attempt.max_score = round(max_total, 2)
    attempt.score = round(max(0.0, total), 2)
    attempt.percentage = round(attempt.score / max_total * 100, 2) if max_total > 0 else 0.0
    attempt.passed = attempt.percentage >= float(attempt.pass_percentage or 0)
    attempt.correct_count, attempt.incorrect_count, attempt.unanswered_count = correct, incorrect, unanswered
