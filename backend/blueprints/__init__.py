"""Blueprint registration."""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from .account import bp as account_bp
    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .public import bp as public_bp
    from .quality import bp as quality_bp
    from .quiz import bp as quiz_bp
    from .student import bp as student_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp)
    app.register_blueprint(account_bp, url_prefix="/account")
    app.register_blueprint(quiz_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(quality_bp, url_prefix="/admin/quality")
