"""Question-bank validation, duplicate detection, quiz publish checks and import."""
from __future__ import annotations

import csv
import difflib
import io
import json
import re

from ..extensions import db
from ..models import DIFFICULTIES, QUESTION_TYPES, AnswerOption, Category, Question, Quiz, QuizQuestion
from ..utils import clean_text, normalize_answer, parse_tags, to_float

BLANK_RE = re.compile(r"_{3,}")


def validate_question(data: dict) -> tuple[dict, dict]:
    """Return (clean_data, field_errors). Pure function: no DB writes."""
    errors: dict[str, str] = {}
    qtype = (data.get("qtype") or "single").strip()
    if qtype not in QUESTION_TYPES:
        errors["qtype"] = "Choose a valid question type."
    text = clean_text(data.get("text"), 2000)
    if len(text) < 5:
        errors["text"] = "Question text must be at least 5 characters."
    if qtype == "fill" and text and not BLANK_RE.search(text):
        errors["text"] = "Fill-in-the-blank questions must contain a blank written as ___ (three underscores)."
    marks = to_float(data.get("marks"), None, 0.25, 100)
    if marks is None:
        errors["marks"] = "Marks must be between 0.25 and 100."
    neg = to_float(data.get("negative_marks") or 0, None, 0, 100)
    if neg is None or (marks is not None and neg > marks):
        errors["negative_marks"] = "Negative marks must be between 0 and the question's marks."
    difficulty = data.get("difficulty") or "medium"
    if difficulty not in DIFFICULTIES:
        errors["difficulty"] = "Choose easy, medium or hard."

    options, accepted = [], []
    if qtype in ("single", "multiple"):
        raw = data.get("options") or []
        seen = set()
        for o in raw:
            t = clean_text(o.get("text"), 500)
            if not t:
                continue
            key = t.casefold()
            if key in seen:
                errors["options"] = f"Duplicate option: “{t}”."
            seen.add(key)
            options.append({"text": t, "is_correct": bool(o.get("is_correct"))})
        n_correct = sum(o["is_correct"] for o in options)
        if len(options) < 2 or len(options) > 8:
            errors["options"] = "Provide between 2 and 8 answer options."
        elif qtype == "single" and n_correct != 1:
            errors["options"] = "Single-choice questions need exactly one correct option."
        elif qtype == "multiple" and n_correct < 1:
            errors["options"] = "Mark at least one correct option."
    elif qtype == "truefalse":
        truth = str(data.get("tf_answer", "")).lower()
        if truth not in ("true", "false"):
            errors["options"] = "Select whether the statement is True or False."
        options = [{"text": "True", "is_correct": truth == "true"}, {"text": "False", "is_correct": truth == "false"}]
    elif qtype in ("short", "fill"):
        raw = data.get("accepted") or []
        if isinstance(raw, str):
            raw = raw.split("|") if "|" in raw else raw.splitlines()
        for a in raw:
            a = clean_text(a, 200)
            if a and normalize_answer(a) not in {normalize_answer(x) for x in accepted}:
                accepted.append(a)
        if not accepted:
            errors["accepted"] = "Provide at least one accepted answer."

    clean = {
        "qtype": qtype, "text": text, "explanation": clean_text(data.get("explanation"), 2000) or None,
        "topic": clean_text(data.get("topic"), 100) or None, "difficulty": difficulty,
        "tags": parse_tags(data.get("tags")), "marks": marks, "negative_marks": neg or 0.0,
        "category_id": data.get("category_id") or None, "options": options, "accepted": accepted,
    }
    return clean, errors


def apply_question(question: Question, clean: dict) -> Question:
    for field in ("qtype", "text", "explanation", "topic", "difficulty", "tags", "marks", "negative_marks",
                  "category_id"):
        setattr(question, field, clean[field])
    question.accepted_answers = json.dumps(clean["accepted"]) if clean["accepted"] else None
    # Replace options. Historical attempts are unaffected because they use snapshots.
    question.options.clear()
    db.session.flush()
    for i, o in enumerate(clean["options"]):
        question.options.append(AnswerOption(text=o["text"], is_correct=o["is_correct"], position=i))
    return question


def similar_questions(text: str, exclude_id: int | None = None, limit: int = 5, threshold: float = 0.72):
    """Search-before-add duplicate detection (Q06)."""
    target = normalize_answer(text)
    if len(target) < 8:
        return []
    out = []
    q = Question.query.with_entities(Question.id, Question.text, Question.is_archived)
    for qid, qtext, archived in q.limit(5000).all():
        if exclude_id and qid == exclude_id:
            continue
        ratio = difflib.SequenceMatcher(None, target, normalize_answer(qtext)).ratio()
        if ratio >= threshold:
            out.append({"id": qid, "text": qtext[:200], "similarity": round(ratio * 100), "archived": archived})
    return sorted(out, key=lambda x: -x["similarity"])[:limit]


def publish_problems(quiz: Quiz) -> list[str]:
    problems = []
    qs = quiz.active_questions
    if not qs:
        problems.append("Add at least one active question.")
    for q in qs:
        if q.qtype in ("single", "truefalse") and sum(o.is_correct for o in q.options) != 1:
            problems.append(f"Question #{q.id} must have exactly one correct option.")
        if q.qtype == "multiple" and not any(o.is_correct for o in q.options):
            problems.append(f"Question #{q.id} has no correct option.")
        if q.qtype in ("short", "fill") and not q.answers_list:
            problems.append(f"Question #{q.id} has no accepted answers.")
    if not (1 <= (quiz.time_limit_minutes or 0) <= 600):
        problems.append("Time limit must be between 1 and 600 minutes.")
    if quiz.start_at and quiz.end_at and quiz.end_at <= quiz.start_at:
        problems.append("End date must be after the start date.")
    if quiz.result_release == "after_close" and not quiz.end_at:
        problems.append("“Release after close” requires an end date.")
    return problems


# ---------------------------------------------------------------------------
# CSV / JSON import (Q02)
# ---------------------------------------------------------------------------

CSV_COLUMNS = ["type", "question", "option_a", "option_b", "option_c", "option_d", "option_e", "option_f",
               "correct", "marks", "negative_marks", "difficulty", "category", "topic", "tags", "explanation"]
LETTERS = "abcdef"


def _row_to_payload(row: dict, categories: dict) -> tuple[dict, list[str]]:
    errs = []
    qtype = (row.get("type") or "single").strip().lower().replace("-", "").replace(" ", "")
    qtype = {"mcq": "single", "single": "single", "multiple": "multiple", "multi": "multiple",
             "truefalse": "truefalse", "tf": "truefalse", "short": "short", "shortanswer": "short",
             "fill": "fill", "fillblank": "fill", "fillintheblank": "fill"}.get(qtype, qtype)
    correct = str(row.get("correct") or "").strip()
    payload = {"qtype": qtype, "text": row.get("question") or row.get("text"), "marks": row.get("marks") or 1,
               "negative_marks": row.get("negative_marks") or 0,
               "difficulty": (row.get("difficulty") or "medium").strip().lower(),
               "topic": row.get("topic"), "tags": row.get("tags"), "explanation": row.get("explanation")}
    cat_name = (row.get("category") or "").strip()
    if cat_name:
        cat = categories.get(cat_name.casefold())
        if cat is None:
            errs.append(f"Unknown category “{cat_name}”.")
        else:
            payload["category_id"] = cat.id
    if qtype in ("single", "multiple"):
        letters = {c.strip().lower() for c in re.split(r"[,;| ]+", correct) if c.strip()}
        payload["options"] = [{"text": row.get(f"option_{l}") or "", "is_correct": l in letters} for l in LETTERS]
        bad = [l for l in letters if l not in LETTERS]
        if bad:
            errs.append("Correct answers must be option letters A-F.")
    elif qtype == "truefalse":
        payload["tf_answer"] = {"t": "true", "true": "true", "f": "false", "false": "false"}.get(correct.lower(), "")
    else:
        payload["accepted"] = correct
    return payload, errs


def parse_import(file_bytes: bytes, filename: str) -> list[dict]:
    name = (filename or "").lower()
    text = file_bytes.decode("utf-8-sig", errors="strict")
    if name.endswith(".json"):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("questions", [])
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of question objects or {\"questions\": [...]}.")
        rows = []
        for d in data:
            if not isinstance(d, dict):
                raise ValueError("Each JSON item must be an object.")
            r = {k: d.get(k) for k in CSV_COLUMNS}
            r["question"] = d.get("question") or d.get("text")
            opts = d.get("options")
            if isinstance(opts, list):
                for i, o in enumerate(opts[:6]):
                    r[f"option_{LETTERS[i]}"] = o
            if isinstance(d.get("correct"), list):
                r["correct"] = ",".join(str(c) for c in d["correct"])
            rows.append({k: ("" if v is None else str(v)) for k, v in r.items()})
        return rows
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "question" not in [f.strip().lower() for f in reader.fieldnames]:
        raise ValueError("CSV must include a header row with at least: type, question, correct.")
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]


def import_questions(rows: list[dict], user_id: int, skip_invalid: bool, quiz: Quiz | None = None) -> dict:
    categories = {c.name.casefold(): c for c in Category.query.all()}
    existing = {normalize_answer(t) for (t,) in Question.query.with_entities(Question.text).all()}
    report = {"created": 0, "duplicates": [], "errors": [], "total": len(rows)}
    valid = []
    seen_in_file = set()
    for idx, row in enumerate(rows, start=2):  # row 1 = header
        payload, errs = _row_to_payload(row, categories)
        clean, field_errs = validate_question(payload)
        errs += list(field_errs.values())
        key = normalize_answer(clean["text"])
        if not errs and (key in existing or key in seen_in_file):
            report["duplicates"].append({"row": idx, "text": clean["text"][:80]})
            continue
        if errs:
            report["errors"].append({"row": idx, "messages": errs})
            continue
        seen_in_file.add(key)
        valid.append(clean)
    if report["errors"] and not skip_invalid:
        report["aborted"] = True
        return report
    try:
        start_pos = len(quiz.question_links) if quiz else 0
        for i, clean in enumerate(valid):
            q = Question(created_by=user_id, text=clean["text"], qtype=clean["qtype"], marks=clean["marks"])
            db.session.add(q)
            apply_question(q, clean)
            if quiz:
                db.session.flush()
                db.session.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, position=start_pos + i))
        db.session.commit()
        report["created"] = len(valid)
    except Exception:
        db.session.rollback()
        raise
    return report
