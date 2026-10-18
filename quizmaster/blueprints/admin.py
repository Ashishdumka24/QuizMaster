"""Administrator area. Every route is protected by ``admin_required`` which
checks the role stored in the database on the server."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for)
from flask_login import current_user
from sqlalchemy import func, or_

from ..extensions import db, limiter
from ..models import (DIFFICULTIES, QUESTION_TYPES, QUIZ_STATUSES, RELEASE_POLICIES, Announcement, AttemptAnswer,
                      AuditLog, Category, EmailOTP, ErrorLog, Feedback, Notification, PasswordResetToken, Question,
                      Quiz, QuizAttempt, QuizQuestion, RequestMetric, SupportMessage, User, Defect)
from ..security import admin_required, json_ok, valid_email, valid_name, validate_password
from ..services import backup as backup_svc
from ..services.attempts import finalize_overdue
from ..services.core import (SETTING_DEFAULTS, cache, get_setting, log_action, notify, notify_role, set_setting)
from ..services.email import EmailDeliveryError, delivery_mode, send_email
from ..services.exports import export
from ..services.grading import grade_attempt
from ..services.questions import (CSV_COLUMNS, apply_question, import_questions, parse_import, publish_problems,
                                  similar_questions, validate_question)
from ..services.stats import admin_overview, quiz_item_analysis, recent_activity, recent_registrations
from ..services.tokens import issue_reset_token
from ..services.uploads import UploadError, delete_upload, save_image
from ..utils import (app_tz, clean_text, fmt_dt, local_input_to_utc, normalize_email, paginate, parse_tags, slugify,
                     to_float, to_int, utcnow)

bp = Blueprint("admin", __name__)


@bp.before_request
@admin_required
def _guard():
    """Applies the admin check to every route in this blueprint."""
    return None


def _date_range():
    """Parse ?from=YYYY-MM-DD&to=YYYY-MM-DD (local dates) into naive-UTC bounds."""
    tz = app_tz()
    start = end = None
    try:
        if request.args.get("from"):
            d = datetime.strptime(request.args["from"], "%Y-%m-%d")
            start = d.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        if request.args.get("to"):
            d = datetime.strptime(request.args["to"], "%Y-%m-%d") + timedelta(days=1)
            end = d.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        flash("Invalid date range ignored. Use the date pickers.", "error")
    return start, end


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@bp.route("/")
def overview():
    finalize_overdue()
    return render_template("admin/overview.html", stats=admin_overview(), activity=recent_activity(),
                           registrations=recent_registrations(),
                           open_support=SupportMessage.query.filter_by(status="open").count(),
                           open_defects=Defect.query.filter(Defect.status.in_(("Open", "In Progress"))).count(),
                           email_mode=delivery_mode())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@bp.route("/users")
def users():
    q = User.query
    search = clean_text(request.args.get("q"), 100)
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if role in ("student", "admin"):
        q = q.filter(User.role == role)
    if status == "active":
        q = q.filter(User.is_active_account.is_(True))
    elif status == "disabled":
        q = q.filter(User.is_active_account.is_(False))
    elif status == "unverified":
        q = q.filter(User.email_verified_at.is_(None))
    sort = request.args.get("sort", "newest")
    order = {"newest": User.created_at.desc(), "name": User.full_name.asc(),
             "last_login": User.last_login_at.desc().nullslast()}.get(sort, User.created_at.desc())
    page = paginate(q.order_by(order), per_page=15)
    counts = dict(db.session.query(QuizAttempt.user_id, func.count(QuizAttempt.id))
                  .filter(QuizAttempt.user_id.in_([u.id for u in page.items] or [0]))
                  .group_by(QuizAttempt.user_id).all())
    return render_template("admin/users.html", page=page, search=search, role=role, status=status, sort=sort,
                           counts=counts)


@bp.route("/users/new", methods=["GET", "POST"])
def user_new():
    errors, form = {}, {"full_name": "", "email": "", "role": "student"}
    if request.method == "POST":
        form = {"full_name": " ".join(clean_text(request.form.get("full_name"), 120).split()),
                "email": normalize_email(request.form.get("email")),
                "role": request.form.get("role") if request.form.get("role") in ("student", "admin") else "student"}
        password = request.form.get("password") or ""
        if not valid_name(form["full_name"]):
            errors["full_name"] = "Enter a valid full name."
        if not valid_email(form["email"]):
            errors["email"] = "Enter a valid email address."
        elif User.query.filter_by(email=form["email"]).first():
            errors["email"] = "A user with this email already exists."
        pw = validate_password(password, form["email"], form["full_name"])
        if pw:
            errors["password"] = " ".join(pw)
        if not errors:
            user = User(full_name=form["full_name"], email=form["email"], role=form["role"],
                        email_verified_at=utcnow(), terms_accepted_at=None)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            log_action("user_created", "user", user.id, f"role={user.role}; by admin")
            notify(user.id, "Welcome to QuizMaster", "Your account was created by an administrator.", None, "info")
            db.session.commit()
            cache.clear("admin:")
            flash(f"User {user.email} created. Share the temporary password securely and ask them to change it.",
                  "success")
            return redirect(url_for("admin.user_detail", user_id=user.id))
    return render_template("admin/user_form.html", errors=errors, form=form)


@bp.route("/users/<int:user_id>")
def user_detail(user_id):
    user = db.session.get(User, user_id) or abort(404)
    attempts = user.attempts.order_by(QuizAttempt.started_at.desc()).limit(20).all()
    logs = AuditLog.query.filter_by(user_id=user.id).order_by(AuditLog.created_at.desc()).limit(15).all()
    return render_template("admin/user_detail.html", user=user, attempts=attempts, logs=logs)


def _last_admin_guard(user: User) -> bool:
    return user.role == "admin" and User.query.filter_by(role="admin", is_active_account=True).count() <= 1


@bp.route("/users/<int:user_id>/action", methods=["POST"])
@limiter.limit("60 per minute")
def user_action(user_id):
    user = db.session.get(User, user_id) or abort(404)
    action = request.form.get("action")
    back = redirect(url_for("admin.user_detail", user_id=user.id))
    if user.id == current_user.id and action in ("make_student", "disable", "delete"):
        flash("You cannot change your own role, disable or delete your own account here.", "error")
        return back
    if action == "make_admin":
        user.role = "admin"
        log_action("role_changed", "user", user.id, "student → admin")
        notify(user.id, "Your role was updated", "You now have administrator access.", None, "info")
        flash(f"{user.full_name} is now an administrator.", "success")
    elif action == "make_student":
        if _last_admin_guard(user):
            flash("At least one active administrator is required.", "error")
            return back
        user.role = "student"
        user.session_version += 1
        log_action("role_changed", "user", user.id, "admin → student")
        flash(f"{user.full_name} is now a student.", "success")
    elif action == "disable":
        if _last_admin_guard(user):
            flash("At least one active administrator is required.", "error")
            return back
        user.is_active_account = False
        user.session_version += 1  # immediately ends their sessions
        log_action("user_disabled", "user", user.id)
        flash(f"{user.full_name}'s account has been disabled and signed out.", "success")
    elif action == "enable":
        user.is_active_account = True
        user.locked_until = None
        user.failed_logins = 0
        log_action("user_enabled", "user", user.id)
        flash(f"{user.full_name}'s account has been enabled.", "success")
    elif action == "verify":
        if not user.is_verified:
            user.email_verified_at = utcnow()
            log_action("user_verified_manually", "user", user.id)
            flash("Email marked as verified.", "success")
    elif action == "unlock":
        user.locked_until = None
        user.failed_logins = 0
        log_action("user_unlocked", "user", user.id)
        flash("Login lock cleared.", "success")
    elif action == "reset_link":
        try:
            mode = issue_reset_token(user)
            log_action("reset_link_sent_by_admin", "user", user.id)
            flash("Password reset link emailed." + (" (Development outbox — not delivered.)" if mode == "outbox"
                                                     else ""), "success")
        except EmailDeliveryError as exc:
            flash(str(exc), "error")
        return back
    elif action == "delete":
        if user.attempts.count():
            flash("This user has quiz history. Disable the account instead to preserve result integrity.", "error")
            return back
        if request.form.get("confirm_email", "").strip().lower() != user.email:
            flash("Type the user's email address exactly to confirm deletion.", "error")
            return back
        avatar = user.avatar_filename
        log_action("user_deleted", "user", user.id, user.email)
        db.session.delete(user)
        db.session.commit()
        delete_upload("avatars", avatar)
        cache.clear("admin:")
        flash("User deleted permanently.", "success")
        return redirect(url_for("admin.users"))
    else:
        abort(400)
    db.session.commit()
    cache.clear("admin:")
    return back


@bp.route("/users/export")
def users_export():
    rows = [[u.id, u.full_name, u.email, u.role, "yes" if u.is_verified else "no",
             "active" if u.is_active_account else "disabled", fmt_dt(u.created_at), fmt_dt(u.last_login_at)]
            for u in User.query.order_by(User.id).all()]
    return export(request.args.get("format", "csv"), "quizmaster-users", "Users",
                  ["ID", "Name", "Email", "Role", "Verified", "Status", "Registered", "Last login"], rows)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORY_ICONS = ["book", "code", "flask", "globe", "calculator", "brain", "trophy", "chart", "music", "palette",
                  "briefcase", "atom", "landmark", "leaf"]


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    errors = {}
    if request.method == "POST":
        cid = to_int(request.form.get("id"))
        name = clean_text(request.form.get("name"), 80)
        color = request.form.get("color") or "#6366F1"
        icon = request.form.get("icon") if request.form.get("icon") in CATEGORY_ICONS else "book"
        if len(name) < 2:
            errors["name"] = "Category name must be at least 2 characters."
        if not (len(color) == 7 and color.startswith("#")):
            color = "#6366F1"
        dup = Category.query.filter(func.lower(Category.name) == name.lower())
        if cid:
            dup = dup.filter(Category.id != cid)
        if name and dup.first():
            errors["name"] = "A category with this name already exists."
        if not errors:
            cat = db.session.get(Category, cid) if cid else Category()
            if cat is None:
                abort(404)
            cat.name, cat.color, cat.icon = name, color, icon
            cat.description = clean_text(request.form.get("description"), 300) or None
            base = slugify(name)
            slug, n = base, 2
            while Category.query.filter(Category.slug == slug, Category.id != (cat.id or 0)).first():
                slug, n = f"{base}-{n}", n + 1
            cat.slug = slug
            if not cid:
                db.session.add(cat)
            db.session.flush()
            log_action("category_updated" if cid else "category_created", "category", cat.id, name)
            db.session.commit()
            flash(f"Category “{name}” saved.", "success")
            return redirect(url_for("admin.categories"))
        flash(next(iter(errors.values())), "error")
    rows = (db.session.query(Category, func.count(func.distinct(Quiz.id)), func.count(func.distinct(Question.id)))
            .outerjoin(Quiz, Quiz.category_id == Category.id)
            .outerjoin(Question, Question.category_id == Category.id)
            .group_by(Category.id).order_by(Category.name).all())
    return render_template("admin/categories.html", rows=rows, icons=CATEGORY_ICONS, errors=errors)


@bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
def category_delete(cat_id):
    cat = db.session.get(Category, cat_id) or abort(404)
    if cat.quizzes.count() or cat.questions.count():
        flash("This category is in use by quizzes or questions. Reassign them before deleting.", "error")
    else:
        log_action("category_deleted", "category", cat.id, cat.name)
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

@bp.route("/quizzes")
def quizzes():
    q = Quiz.query
    search = clean_text(request.args.get("q"), 100)
    status = request.args.get("status", "")
    cat = to_int(request.args.get("category"))
    if search:
        q = q.filter(Quiz.title.ilike(f"%{search}%"))
    if status in QUIZ_STATUSES:
        q = q.filter(Quiz.status == status)
    if cat:
        q = q.filter(Quiz.category_id == cat)
    page = paginate(q.order_by(Quiz.updated_at.desc()), per_page=12)
    attempt_counts = dict(db.session.query(QuizAttempt.quiz_id, func.count(QuizAttempt.id))
                          .group_by(QuizAttempt.quiz_id).all())
    return render_template("admin/quizzes.html", page=page, search=search, status=status, cat=cat,
                           categories=Category.query.order_by(Category.name).all(), attempt_counts=attempt_counts,
                           statuses=QUIZ_STATUSES)


def _quiz_from_form(quiz: Quiz) -> dict:
    f = request.form
    errors = {}
    title = clean_text(f.get("title"), 150)
    if len(title) < 3:
        errors["title"] = "Title must be at least 3 characters."
    dup = Quiz.query.filter(func.lower(Quiz.title) == title.lower())
    if quiz.id:
        dup = dup.filter(Quiz.id != quiz.id)
    if title and dup.first():
        errors["title"] = "Another quiz already uses this title. Choose a distinct title."
    time_limit = to_int(f.get("time_limit_minutes"), None, 1, 600)
    if time_limit is None:
        errors["time_limit_minutes"] = "Time limit must be 1–600 minutes."
    pass_pct = to_float(f.get("pass_percentage"), None, 0, 100)
    if pass_pct is None:
        errors["pass_percentage"] = "Passing threshold must be 0–100%."
    max_attempts = to_int(f.get("max_attempts") or 0, None, 0, 100)
    if max_attempts is None:
        errors["max_attempts"] = "Maximum attempts must be 0 (unlimited) to 100."
    start_at = local_input_to_utc(f.get("start_at"))
    end_at = local_input_to_utc(f.get("end_at"))
    if f.get("start_at") and not start_at:
        errors["start_at"] = "Invalid start date."
    if f.get("end_at") and not end_at:
        errors["end_at"] = "Invalid end date."
    if start_at and end_at and end_at <= start_at:
        errors["end_at"] = "End must be after start."
    release = f.get("result_release") if f.get("result_release") in RELEASE_POLICIES else "immediate"
    if release == "after_close" and not end_at:
        errors["result_release"] = "“After the quiz end date” requires an end date."
    difficulty = f.get("difficulty") if f.get("difficulty") in DIFFICULTIES else "medium"
    category_id = to_int(f.get("category_id"))
    if category_id and not db.session.get(Category, category_id):
        errors["category_id"] = "Choose a valid category."
    if not errors:
        quiz.title = title
        quiz.description = clean_text(f.get("description"), 3000) or None
        quiz.instructions = clean_text(f.get("instructions"), 3000) or None
        quiz.learning_material = clean_text(f.get("learning_material"), 3000) or None
        quiz.category_id = category_id
        quiz.difficulty = difficulty
        quiz.tags = parse_tags(f.get("tags"))
        quiz.time_limit_minutes = time_limit
        quiz.pass_percentage = pass_pct
        quiz.max_attempts = max_attempts
        quiz.start_at, quiz.end_at = start_at, end_at
        quiz.result_release = release
        for flag in ("negative_marking", "shuffle_questions", "shuffle_options", "show_correct_answers",
                     "show_explanations", "featured"):
            setattr(quiz, flag, bool(f.get(flag)))
        if not quiz.slug:
            base = slugify(title)
            slug, n = base, 2
            while Quiz.query.filter_by(slug=slug).first():
                slug, n = f"{base}-{n}", n + 1
            quiz.slug = slug
    return errors


@bp.route("/quizzes/new", methods=["GET", "POST"])
def quiz_new():
    quiz = Quiz(time_limit_minutes=to_int(get_setting("default_time_limit"), 15),
                pass_percentage=to_float(get_setting("default_pass_percentage"), 40.0),
                show_correct_answers=True, show_explanations=True, result_release="immediate", max_attempts=0)
    errors = {}
    if request.method == "POST":
        errors = _quiz_from_form(quiz)
        if not errors:
            quiz.created_by = current_user.id
            quiz.status = "draft"
            db.session.add(quiz)
            db.session.flush()
            log_action("quiz_created", "quiz", quiz.id, quiz.title)
            db.session.commit()
            cache.clear("admin:")
            flash("Quiz created as a draft. Now add questions.", "success")
            return redirect(url_for("admin.quiz_questions", quiz_id=quiz.id))
    return render_template("admin/quiz_form.html", quiz=quiz, errors=errors,
                           categories=Category.query.order_by(Category.name).all())


@bp.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
def quiz_edit(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    errors = {}
    if request.method == "POST":
        errors = _quiz_from_form(quiz)
        if not errors:
            if quiz.status == "published" and publish_problems(quiz):
                db.session.rollback()
                flash("These settings would make the published quiz invalid: " + " ".join(publish_problems(quiz)),
                      "error")
                return redirect(url_for("admin.quiz_edit", quiz_id=quiz_id))
            log_action("quiz_updated", "quiz", quiz.id, quiz.title)
            db.session.commit()
            cache.clear("admin:")
            flash("Quiz settings saved.", "success")
            return redirect(url_for("admin.quiz_edit", quiz_id=quiz.id))
    return render_template("admin/quiz_form.html", quiz=quiz, errors=errors,
                           categories=Category.query.order_by(Category.name).all(),
                           problems=publish_problems(quiz) if quiz.id else [])


@bp.route("/quizzes/<int:quiz_id>/status", methods=["POST"])
def quiz_status(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    target = request.form.get("status")
    if target not in QUIZ_STATUSES:
        abort(400)
    if target == "published":
        problems = publish_problems(quiz)
        if problems:
            flash("Cannot publish yet: " + " ".join(problems), "error")
            return redirect(request.referrer or url_for("admin.quizzes"))
        if not quiz.published_at:
            quiz.published_at = utcnow()
            notify_role("student", f"New quiz: {quiz.title}", (quiz.description or "")[:140],
                        url_for("quiz.detail", slug=quiz.slug), "info")
    old = quiz.status
    quiz.status = target
    log_action("quiz_status", "quiz", quiz.id, f"{old} → {target}")
    db.session.commit()
    cache.clear()
    flash(f"“{quiz.title}” is now {target}.", "success")
    return redirect(request.referrer or url_for("admin.quizzes"))


@bp.route("/quizzes/<int:quiz_id>/publish-results", methods=["POST"])
def quiz_publish_results(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    publish = request.form.get("publish", "1") == "1"
    quiz.results_published = publish
    if publish:
        users = {uid for (uid,) in db.session.query(QuizAttempt.user_id)
                 .filter(QuizAttempt.quiz_id == quiz.id, QuizAttempt.status.in_(("submitted", "expired"))).all()}
        for uid in users:
            notify(uid, f"Results released: {quiz.title}", "Your result and answer review are now available.",
                   url_for("student.history", q=quiz.title), "success")
    log_action("results_published" if publish else "results_hidden", "quiz", quiz.id)
    db.session.commit()
    cache.clear()
    flash("Results published to students." if publish else "Results hidden from students.", "success")
    return redirect(request.referrer or url_for("admin.quizzes"))


@bp.route("/quizzes/<int:quiz_id>/duplicate", methods=["POST"])
def quiz_duplicate(quiz_id):
    src = db.session.get(Quiz, quiz_id) or abort(404)
    copy = Quiz()
    for col in Quiz.__table__.columns.keys():
        if col not in ("id", "slug", "status", "published_at", "created_at", "updated_at", "results_published",
                       "created_by"):
            setattr(copy, col, getattr(src, col))
    base_title = f"{src.title} (copy)"
    title, n = base_title, 2
    while Quiz.query.filter(func.lower(Quiz.title) == title.lower()).first():
        title, n = f"{base_title} {n}", n + 1
    copy.title = title[:150]
    base = slugify(copy.title)
    slug, n = base, 2
    while Quiz.query.filter_by(slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    copy.slug, copy.status, copy.created_by = slug, "draft", current_user.id
    db.session.add(copy)
    db.session.flush()
    for link in src.question_links:
        db.session.add(QuizQuestion(quiz_id=copy.id, question_id=link.question_id, position=link.position))
    log_action("quiz_duplicated", "quiz", copy.id, f"from {src.id}")
    db.session.commit()
    flash("Quiz duplicated as a draft.", "success")
    return redirect(url_for("admin.quiz_edit", quiz_id=copy.id))


@bp.route("/quizzes/<int:quiz_id>/delete", methods=["POST"])
def quiz_delete(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    if quiz.attempts.count():
        flash("This quiz has attempts. Archive it instead so historical results are preserved.", "error")
        return redirect(url_for("admin.quiz_edit", quiz_id=quiz.id))
    log_action("quiz_deleted", "quiz", quiz.id, quiz.title)
    db.session.delete(quiz)
    db.session.commit()
    cache.clear()
    flash("Quiz deleted.", "success")
    return redirect(url_for("admin.quizzes"))


@bp.route("/quizzes/<int:quiz_id>/questions")
def quiz_questions(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    assigned_ids = {l.question_id for l in quiz.question_links}
    q = Question.query.filter(Question.is_archived.is_(False))
    search = clean_text(request.args.get("q"), 100)
    if search:
        q = q.filter(Question.text.ilike(f"%{search}%"))
    cat = to_int(request.args.get("category"))
    if cat:
        q = q.filter(Question.category_id == cat)
    if assigned_ids:
        q = q.filter(~Question.id.in_(assigned_ids))
    page = paginate(q.order_by(Question.created_at.desc()), per_page=10)
    return render_template("admin/quiz_questions.html", quiz=quiz, page=page, search=search, cat=cat,
                           categories=Category.query.order_by(Category.name).all(), problems=publish_problems(quiz))


@bp.route("/quizzes/<int:quiz_id>/questions/update", methods=["POST"])
def quiz_questions_update(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    action = request.form.get("action")
    links = list(quiz.question_links)
    if action == "add":
        ids = [to_int(x) for x in request.form.getlist("question_ids")]
        existing = {l.question_id for l in links}
        pos = len(links)
        added = 0
        for qid in ids:
            if qid and qid not in existing and db.session.get(Question, qid):
                db.session.add(QuizQuestion(quiz_id=quiz.id, question_id=qid, position=pos))
                pos += 1
                added += 1
        flash(f"Added {added} question(s)." if added else "Select at least one question to add.",
              "success" if added else "error")
        log_action("quiz_questions_added", "quiz", quiz.id, f"{added} added")
    elif action == "remove":
        qid = to_int(request.form.get("question_id"))
        link = next((l for l in links if l.question_id == qid), None)
        if link:
            if quiz.status == "published" and len(links) <= 1:
                flash("A published quiz must keep at least one question.", "error")
                return redirect(url_for("admin.quiz_questions", quiz_id=quiz.id))
            db.session.delete(link)
            links.remove(link)
            for i, l in enumerate(links):
                l.position = i
            log_action("quiz_question_removed", "quiz", quiz.id, f"question {qid}")
            flash("Question removed from quiz (it remains in the question bank).", "success")
    elif action in ("up", "down"):
        qid = to_int(request.form.get("question_id"))
        idx = next((i for i, l in enumerate(links) if l.question_id == qid), None)
        swap = (idx - 1) if action == "up" else (idx + 1) if idx is not None else None
        if idx is not None and 0 <= swap < len(links):
            links[idx], links[swap] = links[swap], links[idx]
            for i, l in enumerate(links):
                l.position = i
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.quiz_questions", quiz_id=quiz.id, **({"q": request.form.get("q")}
                                                                       if request.form.get("q") else {})))


@bp.route("/quizzes/<int:quiz_id>/preview")
def quiz_preview(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    return render_template("admin/quiz_preview.html", quiz=quiz, problems=publish_problems(quiz))


@bp.route("/quizzes/<int:quiz_id>/analysis")
def quiz_analysis(quiz_id):
    quiz = db.session.get(Quiz, quiz_id) or abort(404)
    finalize_overdue(quiz_id=quiz.id)
    attempts = QuizAttempt.query.filter(QuizAttempt.quiz_id == quiz.id,
                                        QuizAttempt.status.in_(("submitted", "expired"))).all()
    pcts = [a.percentage or 0 for a in attempts]
    summary = {"n": len(attempts), "avg": round(sum(pcts) / len(pcts), 1) if pcts else None,
               "pass_rate": round(sum(1 for a in attempts if a.passed) / len(attempts) * 100, 1) if attempts else None,
               "avg_time": round(sum(a.time_taken_seconds or 0 for a in attempts) / len(attempts)) if attempts else None}
    return render_template("admin/quiz_analysis.html", quiz=quiz, items=quiz_item_analysis(quiz.id), summary=summary,
                           scores=pcts)


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------

@bp.route("/questions")
def questions():
    q = Question.query
    search = clean_text(request.args.get("q"), 100)
    qtype = request.args.get("type", "")
    difficulty = request.args.get("difficulty", "")
    cat = to_int(request.args.get("category"))
    state = request.args.get("state", "active")
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Question.text.ilike(like), Question.topic.ilike(like), Question.tags.ilike(like)))
    if qtype in QUESTION_TYPES:
        q = q.filter(Question.qtype == qtype)
    if difficulty in DIFFICULTIES:
        q = q.filter(Question.difficulty == difficulty)
    if cat:
        q = q.filter(Question.category_id == cat)
    q = q.filter(Question.is_archived.is_(state == "archived"))
    page = paginate(q.order_by(Question.updated_at.desc()), per_page=15)
    usage = dict(db.session.query(QuizQuestion.question_id, func.count(QuizQuestion.id))
                 .filter(QuizQuestion.question_id.in_([x.id for x in page.items] or [0]))
                 .group_by(QuizQuestion.question_id).all())
    return render_template("admin/questions.html", page=page, search=search, qtype=qtype, difficulty=difficulty,
                           cat=cat, state=state, categories=Category.query.order_by(Category.name).all(), usage=usage,
                           difficulties=DIFFICULTIES)


def _question_payload() -> dict:
    f = request.form
    texts = f.getlist("option_text")
    correct_idx = set(f.getlist("option_correct"))
    options = [{"text": t, "is_correct": str(i) in correct_idx} for i, t in enumerate(texts)]
    return {"qtype": f.get("qtype"), "text": f.get("text"), "explanation": f.get("explanation"),
            "topic": f.get("topic"), "difficulty": f.get("difficulty"), "tags": f.get("tags"),
            "marks": f.get("marks"), "negative_marks": f.get("negative_marks"),
            "category_id": to_int(f.get("category_id")), "options": options, "tf_answer": f.get("tf_answer"),
            "accepted": f.get("accepted", "")}


def _question_form(question: Question, is_new: bool):
    errors = {}
    quiz_id = to_int(request.values.get("quiz_id"))
    quiz = db.session.get(Quiz, quiz_id) if quiz_id else None
    payload = None
    if request.method == "POST":
        payload = _question_payload()
        clean, errors = validate_question(payload)
        if clean["category_id"] and not db.session.get(Category, clean["category_id"]):
            errors["category_id"] = "Choose a valid category."
        if is_new and not errors and not request.form.get("confirm_duplicate"):
            dups = [d for d in similar_questions(clean["text"], threshold=0.9)]
            if dups:
                errors["duplicate"] = "A very similar question already exists (see below). Tick “Save anyway” " \
                                      "if this is intentional."
        image = request.files.get("image")
        new_image = None
        if not errors and image and image.filename:
            try:
                new_image = save_image(image, "questions", current_app.config["QUESTION_IMAGE_MAX_BYTES"], 1200)
            except UploadError as exc:
                errors["image"] = str(exc)
        if not errors:
            if is_new:
                question.created_by = current_user.id
                db.session.add(question)
            apply_question(question, clean)
            old_image = question.image_filename
            if new_image:
                question.image_filename = new_image
            elif request.form.get("remove_image"):
                question.image_filename = None
            db.session.flush()
            if quiz and is_new:
                db.session.add(QuizQuestion(quiz_id=quiz.id, question_id=question.id,
                                            position=len(quiz.question_links)))
            log_action("question_created" if is_new else "question_updated", "question", question.id,
                       clean["text"][:80])
            db.session.commit()
            if old_image and old_image != question.image_filename:
                delete_upload("questions", old_image)
            cache.clear("admin:")
            flash("Question saved." + (" Previously recorded attempts keep their original version." if not is_new
                                       else ""), "success")
            if request.form.get("save_and_new"):
                return redirect(url_for("admin.question_new", quiz_id=quiz.id if quiz else None))
            if quiz:
                return redirect(url_for("admin.quiz_questions", quiz_id=quiz.id))
            return redirect(url_for("admin.questions"))
    form_state = payload or {
        "qtype": question.qtype or "single", "text": question.text or "", "explanation": question.explanation or "",
        "topic": question.topic or "", "difficulty": question.difficulty or "medium", "tags": question.tags or "",
        "marks": question.marks if question.marks is not None else 1, "negative_marks": question.negative_marks or 0,
        "category_id": question.category_id or (quiz.category_id if quiz else None),
        "options": [{"text": o.text, "is_correct": o.is_correct} for o in question.options],
        "tf_answer": next(("true" if o.text == "True" else "false" for o in question.options if o.is_correct), ""),
        "accepted": "\n".join(question.answers_list),
    }
    if form_state.get("qtype") in ("single", "multiple") and len(form_state["options"]) < 4:
        form_state["options"] = form_state["options"] + [{"text": "", "is_correct": False}] * (
            4 - len(form_state["options"]))
    dups = similar_questions(form_state.get("text") or "", exclude_id=question.id) if request.method == "POST" else []
    return render_template("admin/question_form.html", question=question, form=form_state, errors=errors,
                           is_new=is_new, quiz=quiz, dups=dups, categories=Category.query.order_by(Category.name).all(),
                           difficulties=DIFFICULTIES, usage=len(question.quiz_links) if question.id else 0)


@bp.route("/questions/new", methods=["GET", "POST"])
def question_new():
    return _question_form(Question(qtype="single", marks=1.0, difficulty="medium"), True)


@bp.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
def question_edit(question_id):
    return _question_form(db.session.get(Question, question_id) or abort(404), False)


@bp.route("/questions/<int:question_id>/action", methods=["POST"])
def question_action(question_id):
    question = db.session.get(Question, question_id) or abort(404)
    action = request.form.get("action")
    if action == "archive":
        published_only = [l.quiz for l in question.quiz_links if l.quiz.status == "published"
                          and l.quiz.question_count <= 1]
        if published_only:
            flash(f"Cannot archive: it is the only question in published quiz “{published_only[0].title}”.", "error")
            return redirect(request.referrer or url_for("admin.questions"))
        question.is_archived = True
        log_action("question_archived", "question", question.id)
        flash("Question archived. It is hidden from quizzes but kept for history.", "success")
    elif action == "restore":
        question.is_archived = False
        log_action("question_restored", "question", question.id)
        flash("Question restored.", "success")
    elif action == "delete":
        if question.quiz_links:
            flash("This question is used in a quiz. Remove it from quizzes or archive it instead.", "error")
            return redirect(request.referrer or url_for("admin.questions"))
        img = question.image_filename
        log_action("question_deleted", "question", question.id, question.text[:80])
        db.session.delete(question)
        db.session.commit()
        delete_upload("questions", img)
        flash("Question deleted permanently.", "success")
        return redirect(url_for("admin.questions"))
    else:
        abort(400)
    db.session.commit()
    cache.clear("admin:")
    return redirect(request.referrer or url_for("admin.questions"))


@bp.route("/api/questions/similar")
def api_similar():
    return json_ok(similar_questions(request.args.get("text", ""), exclude_id=to_int(request.args.get("exclude"))))


@bp.route("/questions/import", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def questions_import():
    report = None
    quizzes = Quiz.query.filter(Quiz.status != "archived").order_by(Quiz.title).all()
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a CSV or JSON file to import.", "error")
        elif not upload.filename.lower().endswith((".csv", ".json")):
            flash("Only .csv and .json files are supported.", "error")
        else:
            data = upload.read(current_app.config["IMPORT_MAX_BYTES"] + 1)
            if len(data) > current_app.config["IMPORT_MAX_BYTES"]:
                flash("File is too large (max 1 MB).", "error")
            else:
                try:
                    rows = parse_import(data, upload.filename)
                except (ValueError, UnicodeDecodeError) as exc:
                    flash(f"Could not read the file: {exc}", "error")
                    rows = None
                if rows is not None:
                    if not rows:
                        flash("The file contains no question rows.", "error")
                    elif len(rows) > current_app.config["IMPORT_MAX_ROWS"]:
                        flash(f"Too many rows (max {current_app.config['IMPORT_MAX_ROWS']}).", "error")
                    else:
                        quiz = db.session.get(Quiz, to_int(request.form.get("quiz_id"))) \
                            if request.form.get("quiz_id") else None
                        report = import_questions(rows, current_user.id, bool(request.form.get("skip_invalid")),
                                                  quiz)
                        log_action("questions_imported", "question", None,
                                   f"{report['created']} created; {len(report['errors'])} errors; "
                                   f"{len(report['duplicates'])} duplicates; file={upload.filename[:60]}",
                                   commit=True)
                        cache.clear("admin:")
                        if report.get("aborted"):
                            flash("Import cancelled: fix the errors below or tick “Skip invalid rows”. "
                                  "No questions were saved.", "error")
                        else:
                            flash(f"Imported {report['created']} question(s).", "success")
    return render_template("admin/questions_import.html", report=report, quizzes=quizzes, columns=CSV_COLUMNS)


@bp.route("/questions/template.csv")
def questions_template():
    from flask import Response
    sample = (",".join(CSV_COLUMNS) + "\n"
              'single,"What does CPU stand for?",Central Processing Unit,Computer Personal Unit,Central Process Utility,'
              'Control Processing Unit,,,A,1,0,easy,,Hardware,"cpu,basics","The CPU executes instructions."\n'
              'multiple,"Which are Python data types?",list,array,dict,tuple,,,"A,C,D",2,0,medium,,Python,,\n'
              'truefalse,"TQM stands for Total Quality Management.",,,,,,,True,1,0,easy,,TQM,,\n'
              'short,"Which gas do plants absorb from the air?",,,,,,,carbon dioxide|CO2,1,0,easy,,Biology,,\n'
              'fill,"The 80/20 principle is also called the ___ principle.",,,,,,,Pareto,1,0,medium,,TQM,,\n')
    return Response(sample, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=quizmaster-question-template.csv"})


# ---------------------------------------------------------------------------
# Results & attempts
# ---------------------------------------------------------------------------

def _results_query():
    q = QuizAttempt.query.join(User, User.id == QuizAttempt.user_id).join(Quiz, Quiz.id == QuizAttempt.quiz_id)
    quiz_id = to_int(request.args.get("quiz"))
    status = request.args.get("status", "")
    search = clean_text(request.args.get("q"), 100)
    if quiz_id:
        q = q.filter(QuizAttempt.quiz_id == quiz_id)
    if status in ("in_progress", "submitted", "expired"):
        q = q.filter(QuizAttempt.status == status)
    elif status == "passed":
        q = q.filter(QuizAttempt.passed.is_(True))
    elif status == "failed":
        q = q.filter(QuizAttempt.passed.is_(False))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))
    start, end = _date_range()
    if start:
        q = q.filter(QuizAttempt.started_at >= start)
    if end:
        q = q.filter(QuizAttempt.started_at < end)
    return q.order_by(QuizAttempt.started_at.desc())


@bp.route("/results")
def results():
    finalize_overdue()
    page = paginate(_results_query(), per_page=15)
    return render_template("admin/results.html", page=page, quizzes=Quiz.query.order_by(Quiz.title).all(),
                           args=request.args)


@bp.route("/results/export")
def results_export():
    rows = [[a.id, a.user.full_name, a.user.email, a.quiz.title, a.attempt_number, a.status, fmt_dt(a.started_at),
             fmt_dt(a.submitted_at), a.time_taken_seconds or "", a.score if a.score is not None else "", a.max_score,
             a.percentage if a.percentage is not None else "",
             "" if a.passed is None else ("Pass" if a.passed else "Fail")]
            for a in _results_query().limit(5000).all()]
    return export(request.args.get("format", "csv"), "quizmaster-results", "Quiz Results",
                  ["Attempt", "Student", "Email", "Quiz", "#", "Status", "Started", "Submitted", "Seconds", "Score",
                   "Max", "%", "Result"], rows,
                  **({"widths": [12, 30, 42, 46, 6, 18, 30, 30, 14, 12, 10, 10, 12]}
                     if request.args.get("format") == "pdf" else {}))


@bp.route("/results/<int:attempt_id>")
def attempt_detail(attempt_id):
    attempt = db.session.get(QuizAttempt, attempt_id) or abort(404)
    from ..services.attempts import result_released, review_rows
    rows = review_rows(attempt, include_key=True, include_explanations=True) if attempt.is_finished else []
    return render_template("admin/attempt_detail.html", attempt=attempt, rows=rows,
                           released=result_released(attempt))


@bp.route("/results/<int:attempt_id>/override", methods=["POST"])
def attempt_override(attempt_id):
    attempt = db.session.get(QuizAttempt, attempt_id) or abort(404)
    if not attempt.is_finished:
        flash("Only finished attempts can be adjusted.", "error")
        return redirect(url_for("admin.attempt_detail", attempt_id=attempt.id))
    qid = to_int(request.form.get("question_id"))
    question = next((q for q in attempt.snapshot_data.get("questions", []) if q["id"] == qid), None)
    if question is None:
        abort(400)
    marks = to_float(request.form.get("marks"), None, -float(question["marks"]), float(question["marks"]))
    if marks is None:
        flash(f"Marks must be between {-question['marks']} and {question['marks']}.", "error")
        return redirect(url_for("admin.attempt_detail", attempt_id=attempt.id) + f"#q{qid}")
    note = clean_text(request.form.get("note"), 300)
    if len(note) < 3:
        flash("Add a short justification note for the audit trail.", "error")
        return redirect(url_for("admin.attempt_detail", attempt_id=attempt.id) + f"#q{qid}")
    ans = next((a for a in attempt.answers if a.question_id == qid), None)
    if ans is None:
        ans = AttemptAnswer(attempt_id=attempt.id, question_id=qid, response=None)
        db.session.add(ans)
        attempt.answers.append(ans)
    before = ans.marks_awarded
    ans.marks_awarded = marks
    ans.is_correct = marks >= float(question["marks"]) - 1e-9 if request.form.get("correct") is None \
        else request.form.get("correct") == "1"
    ans.manual_override = True
    ans.override_note = note
    old_score = attempt.score
    grade_attempt(attempt)
    attempt.manually_adjusted = True
    log_action("result_override", "attempt", attempt.id,
               f"question {qid}: {before} → {marks}; total {old_score} → {attempt.score}; note: {note}")
    notify(attempt.user_id, f"Result updated: {attempt.quiz.title}",
           f"An instructor reviewed your answers. New score: {attempt.score}/{attempt.max_score}.",
           url_for("quiz.result", attempt_id=attempt.id), "info")
    db.session.commit()
    cache.clear()
    flash(f"Marks updated. New total {attempt.score}/{attempt.max_score} ({attempt.percentage}%).", "success")
    return redirect(url_for("admin.attempt_detail", attempt_id=attempt.id) + f"#q{qid}")


# ---------------------------------------------------------------------------
# Analytics & reports
# ---------------------------------------------------------------------------

@bp.route("/analytics")
def analytics():
    start, end = _date_range()
    q = QuizAttempt.query.filter(QuizAttempt.status.in_(("submitted", "expired")))
    if start:
        q = q.filter(QuizAttempt.submitted_at >= start)
    if end:
        q = q.filter(QuizAttempt.submitted_at < end)
    attempts = q.all()
    per_quiz = {}
    per_day = {}
    from ..utils import to_local
    for a in attempts:
        r = per_quiz.setdefault(a.quiz_id, {"title": a.quiz.title, "n": 0, "sum": 0.0, "passed": 0, "time": 0})
        r["n"] += 1
        r["sum"] += a.percentage or 0
        r["passed"] += 1 if a.passed else 0
        r["time"] += a.time_taken_seconds or 0
        d = to_local(a.submitted_at).strftime("%Y-%m-%d")
        per_day[d] = per_day.get(d, 0) + 1
    quiz_rows = sorted(({"title": r["title"], "attempts": r["n"], "avg": round(r["sum"] / r["n"], 1),
                         "pass_rate": round(r["passed"] / r["n"] * 100, 1), "avg_time": round(r["time"] / r["n"])}
                        for r in per_quiz.values()), key=lambda x: -x["attempts"])
    if request.args.get("format") in ("csv", "xlsx", "pdf"):
        return export(request.args["format"], "quizmaster-quiz-report", "Quiz Performance Report",
                      ["Quiz", "Attempts", "Average %", "Pass rate %", "Avg time (s)"],
                      [[r["title"], r["attempts"], r["avg"], r["pass_rate"], r["avg_time"]] for r in quiz_rows],
                      **({"summary": [("Date range", f"{request.args.get('from') or 'start'} → "
                                                     f"{request.args.get('to') or 'today'}"),
                                      ("Finished attempts", str(len(attempts)))]}
                         if request.args["format"] == "pdf" else {}))
    pcts = [a.percentage or 0 for a in attempts]
    bins = [0] * 10
    for p in pcts:
        bins[min(9, int(p // 10))] += 1
    summary = {"n": len(attempts), "avg": round(sum(pcts) / len(pcts), 1) if pcts else None,
               "pass_rate": round(sum(1 for a in attempts if a.passed) / len(attempts) * 100, 1) if attempts else None,
               "students": len({a.user_id for a in attempts})}
    return render_template("admin/analytics.html", quiz_rows=quiz_rows, summary=summary,
                           day_series=[{"label": k[5:], "value": v} for k, v in sorted(per_day.items())],
                           histogram=[{"label": f"{i * 10}–{i * 10 + 10}", "value": v} for i, v in enumerate(bins)],
                           overview=admin_overview(), args=request.args)


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

@bp.route("/announcements", methods=["GET", "POST"])
def announcements():
    errors, form = {}, {"title": "", "body": "", "audience": "all", "pinned": False}
    edit = db.session.get(Announcement, to_int(request.args.get("edit"))) if request.args.get("edit") else None
    if edit:
        form = {"title": edit.title, "body": edit.body, "audience": edit.audience, "pinned": edit.pinned}
    if request.method == "POST":
        ann = db.session.get(Announcement, to_int(request.form.get("id"))) if request.form.get("id") else None
        form = {"title": clean_text(request.form.get("title"), 150), "body": clean_text(request.form.get("body"), 5000),
                "audience": request.form.get("audience") if request.form.get("audience") in ("all", "students",
                                                                                              "admins") else "all",
                "pinned": bool(request.form.get("pinned"))}
        if len(form["title"]) < 3:
            errors["title"] = "Title must be at least 3 characters."
        if len(form["body"]) < 5:
            errors["body"] = "Write the announcement text."
        if not errors:
            is_new = ann is None
            ann = ann or Announcement(created_by=current_user.id)
            ann.title, ann.body, ann.audience, ann.pinned = form["title"], form["body"], form["audience"], form["pinned"]
            publish_now = request.form.get("publish") == "1"
            if is_new:
                db.session.add(ann)
            db.session.flush()
            if publish_now and not ann.is_published:
                _publish_announcement(ann)
            log_action("announcement_created" if is_new else "announcement_updated", "announcement", ann.id,
                       ann.title)
            db.session.commit()
            flash("Announcement saved" + (" and published." if ann.is_published else " as a draft."), "success")
            return redirect(url_for("admin.announcements"))
        edit = ann
    items = Announcement.query.order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).all()
    return render_template("admin/announcements.html", items=items, form=form, errors=errors, edit=edit)


def _publish_announcement(ann: Announcement) -> None:
    ann.is_published = True
    ann.published_at = utcnow()
    role = {"students": "student", "admins": "admin"}.get(ann.audience)
    notify_role(role, f"📣 {ann.title}", ann.body[:200], url_for("student.dashboard") if role != "admin" else None,
                "info")


@bp.route("/announcements/<int:ann_id>/action", methods=["POST"])
def announcement_action(ann_id):
    ann = db.session.get(Announcement, ann_id) or abort(404)
    action = request.form.get("action")
    if action == "publish":
        _publish_announcement(ann)
        flash("Announcement published and recipients notified.", "success")
    elif action == "unpublish":
        ann.is_published = False
        flash("Announcement moved back to drafts.", "success")
    elif action == "delete":
        log_action("announcement_deleted", "announcement", ann.id, ann.title)
        db.session.delete(ann)
        db.session.commit()
        flash("Announcement deleted.", "success")
        return redirect(url_for("admin.announcements"))
    else:
        abort(400)
    log_action(f"announcement_{action}", "announcement", ann.id)
    db.session.commit()
    return redirect(url_for("admin.announcements"))


# ---------------------------------------------------------------------------
# Inbox: support messages & feedback
# ---------------------------------------------------------------------------

@bp.route("/inbox")
def inbox():
    tab = request.args.get("tab", "support")
    if tab == "feedback":
        page = paginate(Feedback.query.order_by(Feedback.created_at.desc()), per_page=15)
    else:
        status = request.args.get("status", "")
        q = SupportMessage.query
        if status in ("open", "answered", "closed"):
            q = q.filter_by(status=status)
        page = paginate(q.order_by(SupportMessage.created_at.desc()), per_page=15)
    from ..services.quality import ctq_metrics
    return render_template("admin/inbox.html", tab=tab, page=page, fb=ctq_metrics()["feedback"],
                           status=request.args.get("status", ""))


@bp.route("/inbox/<kind>/<int:item_id>", methods=["POST"])
def inbox_update(kind, item_id):
    model = {"support": SupportMessage, "feedback": Feedback}.get(kind) or abort(404)
    item = db.session.get(model, item_id) or abort(404)
    allowed = ("open", "answered", "closed") if kind == "support" else ("new", "reviewed", "actioned")
    status = request.form.get("status")
    if status in allowed:
        item.status = status
    item.admin_note = clean_text(request.form.get("admin_note"), 1000) or item.admin_note
    log_action(f"{kind}_updated", kind, item.id, f"status={item.status}")
    db.session.commit()
    flash("Saved.", "success")
    return redirect(request.referrer or url_for("admin.inbox", tab=kind))


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _audit_query():
    q = AuditLog.query.outerjoin(User, User.id == AuditLog.user_id)
    action = clean_text(request.args.get("action"), 60)
    who = clean_text(request.args.get("user"), 100)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if who:
        q = q.filter(or_(User.email.ilike(f"%{who}%"), User.full_name.ilike(f"%{who}%")))
    start, end = _date_range()
    if start:
        q = q.filter(AuditLog.created_at >= start)
    if end:
        q = q.filter(AuditLog.created_at < end)
    return q.order_by(AuditLog.created_at.desc())


@bp.route("/audit")
def audit():
    actions = [a for (a,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    return render_template("admin/audit.html", page=paginate(_audit_query(), per_page=25), args=request.args,
                           actions=actions)


@bp.route("/audit/export")
def audit_export():
    rows = [[l.id, fmt_dt(l.created_at), l.user.email if l.user else "system", l.action, l.entity_type or "",
             l.entity_id or "", l.details or "", l.ip_address or ""] for l in _audit_query().limit(10000).all()]
    return export(request.args.get("format", "csv"), "quizmaster-audit", "Audit Log",
                  ["ID", "Time", "User", "Action", "Entity", "Entity ID", "Details", "IP"], rows)


# ---------------------------------------------------------------------------
# Settings, backups, maintenance, error logs
# ---------------------------------------------------------------------------

EDITABLE_SETTINGS = ["site_tagline", "registration_open", "maintenance_banner", "default_time_limit",
                     "default_pass_percentage", "leaderboard_enabled", "auto_backup_hours", "support_hours"]


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    errors = {}
    if request.method == "POST":
        values = {k: clean_text(request.form.get(k), 300) for k in EDITABLE_SETTINGS}
        for flag in ("registration_open", "leaderboard_enabled"):
            values[flag] = "true" if request.form.get(flag) else "false"
        if to_int(values["default_time_limit"], None, 1, 600) is None:
            errors["default_time_limit"] = "1–600 minutes."
        if to_float(values["default_pass_percentage"], None, 0, 100) is None:
            errors["default_pass_percentage"] = "0–100%."
        if to_int(values["auto_backup_hours"], None, 1, 720) is None:
            errors["auto_backup_hours"] = "1–720 hours."
        if not errors:
            changed = [k for k in EDITABLE_SETTINGS if get_setting(k) != values[k]]
            for k in EDITABLE_SETTINGS:
                set_setting(k, values[k])
            log_action("settings_updated", "settings", None, ", ".join(changed) or "no changes")
            db.session.commit()
            flash("Settings saved.", "success")
            return redirect(url_for("admin.settings"))
    current = {k: get_setting(k) for k in EDITABLE_SETTINGS}
    if request.method == "POST":
        current.update({k: request.form.get(k, "") for k in EDITABLE_SETTINGS})
    cfg = current_app.config
    return render_template("admin/settings.html", s=current, errors=errors, email_mode=delivery_mode(),
                           mail_server=cfg.get("MAIL_SERVER"), sender=cfg.get("MAIL_DEFAULT_SENDER"),
                           defaults=SETTING_DEFAULTS)


@bp.route("/settings/test-email", methods=["POST"])
@limiter.limit("3 per minute")
def settings_test_email():
    try:
        mode = send_email(current_user.email, "QuizMaster test email", "test_email", user=current_user)
        log_action("test_email_sent", "settings", None, mode)
        db.session.commit()
        if mode == "smtp":
            flash(f"Test email sent to {current_user.email} via SMTP. Check your inbox (and spam folder).", "success")
        else:
            flash("SMTP is not configured: the test email was written to the development outbox only.", "info")
    except EmailDeliveryError as exc:
        flash(f"Test email failed: {exc}", "error")
    return redirect(url_for("admin.settings"))


@bp.route("/backups", methods=["GET", "POST"])
def backups():
    if request.method == "POST":
        try:
            path = backup_svc.create_backup("manual")
            log_action("backup_created", "backup", None, path.name)
            db.session.commit()
            flash(f"Backup created: {path.name}", "success")
        except backup_svc.BackupError as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.backups"))
    return render_template("admin/backups.html", items=backup_svc.list_backups(),
                           last_auto=get_setting("last_auto_backup"), hours=get_setting("auto_backup_hours"),
                           auto_enabled=current_app.config.get("AUTO_BACKUP_ENABLED"))


@bp.route("/backups/<name>")
def backup_download(name):
    path = backup_svc.resolve_backup(name) or abort(404)
    log_action("backup_downloaded", "backup", None, name, commit=True)
    return send_file(path, as_attachment=True, download_name=name, mimetype="application/x-sqlite3")


@bp.route("/maintenance", methods=["GET", "POST"])
def maintenance():
    if request.method == "POST":
        days = to_int(request.form.get("days"), 30, 1, 3650)
        cutoff = utcnow() - timedelta(days=days)
        target = request.form.get("target")
        if target == "metrics":
            n = RequestMetric.query.filter(RequestMetric.created_at < cutoff).delete()
        elif target == "notifications":
            n = Notification.query.filter(Notification.read_at.isnot(None), Notification.created_at < cutoff).delete()
        elif target == "tokens":
            now = utcnow()
            n = EmailOTP.query.filter(EmailOTP.expires_at < now).delete()
            n += PasswordResetToken.query.filter(or_(PasswordResetToken.expires_at < now,
                                                     PasswordResetToken.used_at.isnot(None))).delete()
        elif target == "errors":
            n = ErrorLog.query.filter(ErrorLog.resolved.is_(True), ErrorLog.created_at < cutoff).delete()
        else:
            abort(400)
        log_action("purge", "maintenance", None, f"{target}: {n} rows older than {days} days")
        db.session.commit()
        flash(f"Purged {n} record(s).", "success")
        return redirect(url_for("admin.maintenance"))
    counts = {"metrics": RequestMetric.query.count(),
              "notifications": Notification.query.filter(Notification.read_at.isnot(None)).count(),
              "tokens": EmailOTP.query.count() + PasswordResetToken.query.count(),
              "errors": ErrorLog.query.filter_by(resolved=True).count()}
    return render_template("admin/maintenance.html", counts=counts)


@bp.route("/errors")
def errors():
    show = request.args.get("show", "open")
    q = ErrorLog.query
    if show == "open":
        q = q.filter_by(resolved=False)
    return render_template("admin/errors.html", page=paginate(q.order_by(ErrorLog.created_at.desc()), per_page=20),
                           show=show)


@bp.route("/errors/<int:err_id>/action", methods=["POST"])
def error_action(err_id):
    err = db.session.get(ErrorLog, err_id) or abort(404)
    action = request.form.get("action")
    if action == "resolve":
        err.resolved = True
        flash("Marked as resolved.", "success")
    elif action == "to_defect":
        d = Defect(title=f"{err.error_type} at {err.path}"[:160], description=(err.message or "")[:2000],
                   defect_type="Other", severity="High", status="Open", source="error_log",
                   fishbone_category="Software Code", module=err.path, reported_by=current_user.id)
        db.session.add(d)
        db.session.flush()
        d.code = f"DEF-{d.id:03d}"
        err.resolved = True
        log_action("defect_from_error", "defect", d.id, d.code)
        db.session.commit()
        flash(f"Defect {d.code} created from the error log.", "success")
        return redirect(url_for("quality.defect_edit", defect_id=d.id))
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.errors"))
