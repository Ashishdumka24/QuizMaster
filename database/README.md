# Database

* `migrations/`: Alembic migration scripts (managed with Flask-Migrate). `python app.py` applies
  them automatically. To apply them by hand, run `flask --app app db upgrade`.
* The SQLite database file is created at runtime in `../instance/quizmaster.db`. That folder is
  git-ignored because it holds live data, uploads, backups, logs and the dev email outbox.
* To use PostgreSQL instead, set `DATABASE_URL` in `.env` (see `.env.example`).

After changing a model, create a migration:

```
flask --app app db migrate -m "describe the change"
flask --app app db upgrade
```
