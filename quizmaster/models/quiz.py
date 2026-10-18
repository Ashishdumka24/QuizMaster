"""Categories, question bank, quizzes, attempts and submitted answers."""
from __future__ import annotations

import json

from ..extensions import db
from ..utils import utcnow

QUESTION_TYPES = {
    "single": "Single choice",
    "multiple": "Multiple select",
    "truefalse": "True / False",
    "short": "Short answer",
    "fill": "Fill in the blank",
}
DIFFICULTIES = ("easy", "medium", "hard")
QUIZ_STATUSES = ("draft", "published", "closed", "archived")
RELEASE_POLICIES = {
    "immediate": "Immediately after submission",
    "after_close": "After the quiz end date",
    "manual": "When an administrator publishes results",
}
ATTEMPT_STATUSES = ("in_progress", "submitted", "expired")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(90), nullable=False, unique=True, index=True)
    description = db.Column(db.String(300))
    color = db.Column(db.String(9), nullable=False, default="#6366F1")
    icon = db.Column(db.String(30), nullable=False, default="book")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    quizzes = db.relationship("Quiz", back_populates="category", lazy="dynamic")
    questions = db.relationship("Question", back_populates="category", lazy="dynamic")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    qtype = db.Column(db.String(12), nullable=False, default="single", index=True)
    text = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    topic = db.Column(db.String(100))
    difficulty = db.Column(db.String(10), nullable=False, default="medium", index=True)
    tags = db.Column(db.String(330))
    marks = db.Column(db.Float, nullable=False, default=1.0)
    negative_marks = db.Column(db.Float, nullable=False, default=0.0)
    # JSON list of accepted answers for short / fill-in-the-blank questions.
    accepted_answers = db.Column(db.Text)
    image_filename = db.Column(db.String(80))
    is_archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    category = db.relationship("Category", back_populates="questions")
    options = db.relationship("AnswerOption", back_populates="question", order_by="AnswerOption.position",
                              cascade="all, delete-orphan")
    quiz_links = db.relationship("QuizQuestion", back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("marks > 0", name="marks_positive"),
        db.CheckConstraint("negative_marks >= 0", name="negative_non_negative"),
    )

    @property
    def type_label(self) -> str:
        return QUESTION_TYPES.get(self.qtype, self.qtype)

    @property
    def answers_list(self) -> list[str]:
        try:
            data = json.loads(self.accepted_answers or "[]")
            return [str(a) for a in data if str(a).strip()]
        except (ValueError, TypeError):
            return []

    @property
    def is_choice(self) -> bool:
        return self.qtype in ("single", "multiple", "truefalse")

    @property
    def tag_list(self) -> list[str]:
        return [t for t in (self.tags or "").split(",") if t]


class AnswerOption(db.Model):
    __tablename__ = "answer_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    question = db.relationship("Question", back_populates="options")


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(170), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    difficulty = db.Column(db.String(10), nullable=False, default="medium", index=True)
    tags = db.Column(db.String(330))
    time_limit_minutes = db.Column(db.Integer, nullable=False, default=10)
    pass_percentage = db.Column(db.Float, nullable=False, default=40.0)
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    max_attempts = db.Column(db.Integer, nullable=False, default=0)  # 0 = unlimited
    negative_marking = db.Column(db.Boolean, nullable=False, default=False)
    shuffle_questions = db.Column(db.Boolean, nullable=False, default=False)
    shuffle_options = db.Column(db.Boolean, nullable=False, default=False)
    result_release = db.Column(db.String(12), nullable=False, default="immediate")
    results_published = db.Column(db.Boolean, nullable=False, default=False)
    show_correct_answers = db.Column(db.Boolean, nullable=False, default=True)
    show_explanations = db.Column(db.Boolean, nullable=False, default=True)
    learning_material = db.Column(db.Text)
    status = db.Column(db.String(12), nullable=False, default="draft", index=True)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    category = db.relationship("Category", back_populates="quizzes")
    question_links = db.relationship("QuizQuestion", back_populates="quiz", order_by="QuizQuestion.position",
                                     cascade="all, delete-orphan")
    attempts = db.relationship("QuizAttempt", back_populates="quiz", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint("time_limit_minutes >= 1 AND time_limit_minutes <= 600", name="time_limit_range"),
        db.CheckConstraint("pass_percentage >= 0 AND pass_percentage <= 100", name="pass_range"),
        db.CheckConstraint("max_attempts >= 0", name="max_attempts_non_negative"),
    )

    @property
    def active_questions(self) -> list["Question"]:
        return [link.question for link in self.question_links if link.question and not link.question.is_archived]

    @property
    def question_count(self) -> int:
        return len(self.active_questions)

    @property
    def total_marks(self) -> float:
        return round(sum(q.marks for q in self.active_questions), 2)

    @property
    def tag_list(self) -> list[str]:
        return [t for t in (self.tags or "").split(",") if t]


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    quiz = db.relationship("Quiz", back_populates="question_links")
    question = db.relationship("Question", back_populates="quiz_links")

    __table_args__ = (db.UniqueConstraint("quiz_id", "question_id", name="uq_quiz_question_pair"),)


class QuizAttempt(db.Model):
    """One attempt by one user at one quiz.

    The result of an attempt (score, percentage, pass/fail) lives on this row, so
    there can never be more than one result per attempt. `snapshot` freezes the
    exact questions, options, marks and answer key at start time, which keeps
    historical scores stable even if an administrator later edits a question.
    """

    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(12), nullable=False, default="in_progress", index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    deadline_at = db.Column(db.DateTime, nullable=False)
    submitted_at = db.Column(db.DateTime, index=True)
    time_taken_seconds = db.Column(db.Integer)
    score = db.Column(db.Float)
    max_score = db.Column(db.Float, nullable=False, default=0)
    percentage = db.Column(db.Float)
    passed = db.Column(db.Boolean)
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    incorrect_count = db.Column(db.Integer, nullable=False, default=0)
    unanswered_count = db.Column(db.Integer, nullable=False, default=0)
    pass_percentage = db.Column(db.Float, nullable=False, default=40.0)
    negative_marking = db.Column(db.Boolean, nullable=False, default=False)
    snapshot = db.Column(db.Text, nullable=False)
    auto_submitted = db.Column(db.Boolean, nullable=False, default=False)
    manually_adjusted = db.Column(db.Boolean, nullable=False, default=False)
    grading_ms = db.Column(db.Float)        # server-side grading time (TQM CTQ metric)
    submit_latency_ms = db.Column(db.Float)  # full submission request processing time
    client_ip = db.Column(db.String(64))

    user = db.relationship("User", back_populates="attempts")
    quiz = db.relationship("Quiz", back_populates="attempts")
    answers = db.relationship("AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("user_id", "quiz_id", "attempt_number", name="uq_attempt_number"),
        db.Index("ix_attempt_quiz_status", "quiz_id", "status"),
    )

    @property
    def snapshot_data(self) -> dict:
        try:
            return json.loads(self.snapshot or "{}")
        except (ValueError, TypeError):
            return {}

    @property
    def is_finished(self) -> bool:
        return self.status in ("submitted", "expired")


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, nullable=False)  # refers to snapshot question id
    response = db.Column(db.Text)  # JSON: list of option ids, or {"text": "..."}
    marked_for_review = db.Column(db.Boolean, nullable=False, default=False)
    is_correct = db.Column(db.Boolean)
    marks_awarded = db.Column(db.Float)
    manual_override = db.Column(db.Boolean, nullable=False, default=False)
    override_note = db.Column(db.String(300))
    answered_at = db.Column(db.DateTime, default=utcnow)

    attempt = db.relationship("QuizAttempt", back_populates="answers")

    __table_args__ = (db.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answer"),)

    @property
    def response_data(self):
        try:
            return json.loads(self.response) if self.response else None
        except (ValueError, TypeError):
            return None
