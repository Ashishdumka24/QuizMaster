# Backend — Flask application (Python package `backend`)

Handles routing, business rules, security, the database models, grading and the TQM analytics.
Templates and static files are loaded from `../frontend` (see `config.py` → `TEMPLATES_DIR`, `STATIC_DIR`).

```
backend/
├── __init__.py        create_app(): config, extensions, blueprints, security headers, logging
├── config.py          environment-driven settings and project paths (reads ../.env)
├── extensions.py      SQLAlchemy, Migrate, CSRF, Limiter, Login, Compress, Cache
├── security.py        role_required, password policy, security headers, safe redirects
├── bootstrap.py       migrate → seed → optional first admin (used by app.py)
├── cli.py             flask commands: create-admin, seed, backup, restore-backup, generate-charts, purge
├── seed.py            categories, sample quizzes, FMEA baseline, real development defects
├── quality_goals.py   Q01–Q20 from the BBAT104 guidelines → where each is implemented
├── icons.py           inline SVG icon set used by the templates
├── utils.py           pagination, time-zone and formatting helpers
├── models/            user · quiz (questions, attempts, snapshots) · quality (defects, FMEA, PDCA) · system
├── blueprints/        public · auth · student · account · quiz (+ JSON API) · admin · quality (TQM)
└── services/          email · tokens (OTP/reset) · attempts · grading · stats · quality · charts
                       (Matplotlib) · exports (CSV/Excel/PDF) · backup · uploads · questions (import)
```
