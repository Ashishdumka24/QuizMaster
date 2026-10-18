"""TQM records: defect log / check sheet, FMEA, PDCA actions and version log."""
from __future__ import annotations

from ..extensions import db
from ..utils import utcnow

# Ishikawa categories prescribed by the BBAT104 guideline (section 6.3).
FISHBONE_CATEGORIES = ("People", "Process", "Software Code", "Infrastructure")
DEFECT_TYPES = (
    "Validation", "Authentication", "Grading / Scoring", "Timer / Submission",
    "UI / Layout", "Performance", "Data Integrity", "Email / Notification",
    "Configuration", "Documentation", "Other",
)
SEVERITIES = ("Low", "Medium", "High", "Critical")
DEFECT_STATUSES = ("Open", "In Progress", "Resolved", "Verified", "Closed")
DEFECT_SOURCES = {
    "development": "Found during development / code review",
    "testing": "Found in automated or manual testing",
    "user_report": "Reported by a user (bug report form)",
    "error_log": "Captured automatically from the error log",
}
PDCA_STAGES = ("Plan", "Do", "Check", "Act", "Closed")


class Defect(db.Model):
    __tablename__ = "defects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    module = db.Column(db.String(60))
    defect_type = db.Column(db.String(40), nullable=False, default="Other", index=True)
    fishbone_category = db.Column(db.String(20), nullable=False, default="Software Code")
    severity = db.Column(db.String(10), nullable=False, default="Medium")
    status = db.Column(db.String(12), nullable=False, default="Open", index=True)
    source = db.Column(db.String(15), nullable=False, default="development")
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    preventive_action = db.Column(db.Text)
    steps_to_reproduce = db.Column(db.Text)
    reported_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reporter_email = db.Column(db.String(254))
    occurrences = db.Column(db.Integer, nullable=False, default=1)
    detected_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    resolved_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    reporter = db.relationship("User")

    __table_args__ = (db.CheckConstraint("occurrences >= 1", name="occurrences_positive"),)


class FMEAItem(db.Model):
    __tablename__ = "fmea_items"

    id = db.Column(db.Integer, primary_key=True)
    process_step = db.Column(db.String(100), nullable=False)
    failure_mode = db.Column(db.String(200), nullable=False)
    effect = db.Column(db.String(300), nullable=False)
    cause = db.Column(db.String(300), nullable=False)
    current_controls = db.Column(db.String(300))
    severity = db.Column(db.Integer, nullable=False)
    occurrence = db.Column(db.Integer, nullable=False)
    detection = db.Column(db.Integer, nullable=False)
    recommended_action = db.Column(db.String(400))
    owner = db.Column(db.String(80))
    action_status = db.Column(db.String(15), nullable=False, default="Planned")  # Planned | Implemented | Verified
    new_severity = db.Column(db.Integer)
    new_occurrence = db.Column(db.Integer)
    new_detection = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.CheckConstraint("severity BETWEEN 1 AND 10", name="sev_range"),
        db.CheckConstraint("occurrence BETWEEN 1 AND 10", name="occ_range"),
        db.CheckConstraint("detection BETWEEN 1 AND 10", name="det_range"),
    )

    @property
    def rpn(self) -> int:
        return int(self.severity) * int(self.occurrence) * int(self.detection)

    @property
    def new_rpn(self) -> int | None:
        if self.new_severity and self.new_occurrence and self.new_detection:
            return int(self.new_severity) * int(self.new_occurrence) * int(self.new_detection)
        return None

    @property
    def risk_level(self) -> str:
        r = self.rpn
        return "Critical" if r >= 200 else "High" if r >= 120 else "Medium" if r >= 60 else "Low"


class PDCAAction(db.Model):
    __tablename__ = "pdca_actions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    objective = db.Column(db.String(300))
    plan = db.Column(db.Text)
    do = db.Column(db.Text)
    check = db.Column(db.Text)
    act = db.Column(db.Text)
    stage = db.Column(db.String(10), nullable=False, default="Plan")
    metric_name = db.Column(db.String(100))
    baseline_value = db.Column(db.String(60))
    target_value = db.Column(db.String(60))
    result_value = db.Column(db.String(60))
    defect_id = db.Column(db.Integer, db.ForeignKey("defects.id", ondelete="SET NULL"))
    owner = db.Column(db.String(80))
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    defect = db.relationship("Defect")


class ChangelogEntry(db.Model):
    """Version log (Q19)."""

    __tablename__ = "changelog"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    changes = db.Column(db.Text, nullable=False)  # one change per line
    change_type = db.Column(db.String(15), nullable=False, default="feature")  # feature | fix | improvement | security
    released_on = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
