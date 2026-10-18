"""Create clearly-labelled DEMO activity so dashboards and SQC charts have data.

    python scripts/demo_activity.py --students 4 --attempts 3

What it does (and does not do):
* Creates demo student accounts named "Demo Student N" with e-mails
  ``demo.studentN@quizmaster.local`` and a random password (printed once).
* Logs each one in through the real HTTP routes (Flask test client, in-process)
  and takes published quizzes through the same JSON API the browser uses,
  choosing answers at random. Timings recorded are therefore genuine server
  processing times on *this* machine, but the students and their answers are
  synthetic. Never present these numbers as real user data.
* It does NOT create feedback ratings, so CSAT stays "awaiting data" until
  real users submit feedback.

Remove demo data at any time: Admin → Users → search "demo.student" → delete.
"""
import argparse
import os
import random
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402
from quizmaster.bootstrap import prepare_database  # noqa: E402
from quizmaster.extensions import db, limiter  # noqa: E402
from quizmaster.models import Quiz, User  # noqa: E402
from quizmaster.utils import utcnow  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--students", type=int, default=4)
    ap.add_argument("--attempts", type=int, default=3, help="quizzes attempted per student")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    app.config.update(WTF_CSRF_ENABLED=False)
    limiter.enabled = False  # local script only; the running server keeps its limits
    with app.app_context():
        prepare_database(app)
    creds = []
    with app.app_context():
        for n in range(1, args.students + 1):
            email = f"demo.student{n}@quizmaster.local"
            if not User.query.filter_by(email=email).first():
                pw = "Demo#" + secrets.token_urlsafe(9)
                u = User(full_name=f"Demo Student {n}", email=email, role="student", email_verified_at=utcnow())
                u.set_password(pw)
                db.session.add(u)
                creds.append((email, pw))
        db.session.commit()
        quizzes = [(q.slug, q.title) for q in Quiz.query.filter_by(status="published").all()]
    known = {e: p for e, p in creds}
    total = 0
    for n in range(1, args.students + 1):
        email = f"demo.student{n}@quizmaster.local"
        if email not in known:
            continue  # existing account: password unknown, skip
        c = app.test_client()
        c.post("/auth/login", data={"email": email, "password": known[email]})
        for slug, title in rng.sample(quizzes, min(args.attempts, len(quizzes))):
            r = c.post(f"/quizzes/{slug}/start")
            if r.status_code != 302 or "/attempts/" not in (r.location or ""):
                continue
            aid = int(r.location.rstrip("/").split("/")[-1])
            state = c.get(f"/api/attempts/{aid}/state").get_json()["data"]
            for q in state["questions"]:
                if rng.random() < 0.08:
                    continue  # leave some unanswered
                if q.get("options"):
                    ids = [o["id"] for o in q["options"]]
                    pick = rng.sample(ids, 2) if q["type"] == "multiple" and len(ids) > 2 else [rng.choice(ids)]
                    resp = {"options": pick}
                else:
                    resp = {"text": rng.choice(["act", "pareto", "sipoc", "42", "kaizen"])}
                c.post(f"/api/attempts/{aid}/answers", json={"answers": [{"question_id": q["id"], "response": resp}]})
            c.post(f"/api/attempts/{aid}/submit", json={})
            total += 1
    print(f"Demo activity: {total} attempts by {len(creds)} new demo students (synthetic, labelled 'Demo').")
    for e, p in creds:
        print(f"  {e}  password: {p}")


if __name__ == "__main__":
    main()
