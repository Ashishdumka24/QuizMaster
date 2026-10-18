"""
QuizMaster — development entry point.

    python app.py            → http://127.0.0.1:5000

On start-up this script applies database migrations, inserts the base content
(categories, sample quizzes, TQM baseline records) when the database is empty,
and optionally bootstraps the first administrator from environment variables.
For production use a WSGI server with `wsgi.py` (see docs/DEPLOYMENT.md).
"""
import os

from backend import create_app
from backend.bootstrap import prepare_database

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        prepare_database(app)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  QuizMaster is running →  http://{'127.0.0.1' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}\n")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False), use_reloader=app.config.get("DEBUG", False))
