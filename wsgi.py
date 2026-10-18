"""Production WSGI entry point.

    gunicorn -w 3 -b 0.0.0.0:8000 wsgi:app          (Linux)
    waitress-serve --listen=0.0.0.0:8000 wsgi:app    (Windows / cross-platform)

Run `flask --app wsgi db upgrade` during each deployment before starting.
"""
from quizmaster import create_app

app = create_app()
