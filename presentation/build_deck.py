"""Builds QuizMaster_Presentation.pptx - an 11-slide, widescreen deck.

Design: deep-navy creative backgrounds, QuizMaster brand gradient
(indigo -> violet -> cyan), real app screenshots in browser/phone frames,
point-form copy, manual slide advance with smooth transitions, gentle
staggered fade-in animations, and presenter notes on every slide.

Every technical fact (features, quality goals Q01-Q20, table/route/test
counts, CTQ metrics, defect numbers) is taken from the repository itself.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from deck_helpers import *  # palette, helpers, Animator, Inches, etc.
from deck_helpers import (set_gradient, set_shadow, rounded_pic)

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda name: os.path.join(HERE, "assets", name)
OUT = os.path.join(os.path.dirname(HERE), "QuizMaster_Presentation.pptx")

prs = Presentation()
prs.slide_width = Inches(SLIDE_W)
prs.slide_height = Inches(SLIDE_H)
BLANK = prs.slide_layouts[6]
for lay in prs.slide_layouts:
    if lay.name == "Blank":
        BLANK = lay
        break


def new_slide(bg, transition="fade", direction=None):
    s = prs.slides.add_slide(BLANK)
    add_bg(s, A(bg))
    set_transition(s, transition, direction)
    return s


# =========================================================================== #
# SLIDE 1 - COVER                                                             #
# =========================================================================== #
s = new_slide("bg_cover.jpg", "fade")
anim = Animator(s)

logo = s.shapes.add_picture(A("logo.png"), Inches(0.57), Inches(0.40),
                            Inches(0.50), Inches(0.50))
wm, tf = tb(s, 1.16, 0.40, 3.4, 0.52, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True)
run(p, "Quiz", size=21, color=WHITE, bold=True, font=HEAD)
run(p, "Master", size=21, color=WHITE, bold=True, font=HEAD, gradient=True)
top_chip = chip(s, 9.06, 0.46, 3.70, 0.36,
                "ONLINE QUIZ · ASSESSMENT · TQM", size=9.5, color=IND_L,
                bold=True)
anim.fade(logo, wm, top_chip, delay=0)

_, tf = tb(s, MX, 1.48, 6.15, 0.35)
p = para(tf, first=True)
run(p, "LEARN SMARTER · ASSESS BETTER · IMPROVE CONTINUOUSLY", size=10.5,
    color=CYAN_L, bold=True, spc=1.2)
eyebrow = _
anim.fade(eyebrow, delay=120)

hl, tf = tb(s, MX, 1.80, 6.1, 2.25)
p = para(tf, first=True, line=1.04)
run(p, "Quizzes that", size=36, color=WHITE, bold=True, font=HEAD)
p = para(tf, line=1.04)
run(p, "grade instantly", size=36, color=WHITE, bold=True, font=HEAD,
    gradient=True)
p = para(tf, line=1.04)
run(p, "and keep improving.", size=36, color=WHITE, bold=True, font=HEAD)
anim.fade(hl, delay=240)

pts = bullets(s, MX, 4.08, 5.75, 1.9, [
    ("One platform ", "— students, administrators & quality teams"),
    ("Timed quizzes ", "with instant, server-side auto-grading"),
    ("Live analytics ", "— scores, trends, leaderboards & reports"),
    ("Built-in TQM workspace ", "— Pareto · Fishbone · FMEA · PDCA"),
], size=13, gap=8)
anim.fade(pts, delay=420)

stats = [("22", "database tables"), ("110+", "application routes"),
         ("20", "quality goals mapped"), ("50+", "automated tests")]
stat_shapes = []
for i, (num, lab) in enumerate(stats):
    bx, tf = tb(s, MX + i * 1.52, 6.02, 1.5, 0.85)
    p = para(tf, first=True, line=1.0)
    run(p, num, size=22, color=WHITE, bold=True, font=HEAD, gradient=True)
    p = para(tf, line=1.05)
    run(p, lab, size=9.5, color=MUTED)
    stat_shapes.append(bx)
anim.fade(*stat_shapes, delay=600)

bshapes, _ = browser(s, A("home.jpg"), 6.78, 1.50, 6.02, ratio=1.60,
                     url="quizmaster.app")
anim.fade(*bshapes, delay=340)
pshapes, _ = phone(s, A("mobile.jpg"), 6.22, 3.62, 1.52, ratio=0.52)
anim.fade(*pshapes, delay=720)

_, tf = tb(s, MX, 7.08, 7.6, 0.3)
p = para(tf, first=True)
run(p, "Presented by ", size=10.5, color=MUTED)
run(p, "Ashish", size=10.5, color=WHITE, bold=True)
run(p, "   ·   Fundamentals of TQM (BBAT104) — Project Presentation",
    size=10.5, color=MUTED)
_, tf = tb(s, 8.4, 7.08, 4.36, 0.3)
p = para(tf, first=True, align=PP_ALIGN.RIGHT)
run(p, "github.com/Ashishdumka24/QuizMaster", size=10.5, color=FAINT)
anim.build()
notes(s, "Welcome everyone. This is QuizMaster - my online quiz, assessment "
         "and Total Quality Management platform. In one line: students take "
         "timed quizzes that are graded the instant they submit, "
         "administrators manage everything from one console, and a built-in "
         "TQM workspace keeps improving the system using real data. It runs "
         "in any browser, on phone or desktop, and everything I will show "
         "today is a real, working application.")

# =========================================================================== #
# SLIDE 2 - THE PROBLEM (problem statement + baseline)                        #
# =========================================================================== #
s = new_slide("bg_content.jpg", "push", "l")
anim = Animator(s)
anim.fade(*header(s, "Why QuizMaster · Problem statement",
                  [("Assessment today is ", False),
                   ("slow, manual & blind", True)],
                  "The baseline — how quizzes still run in most classrooms, and what it costs."),
          delay=0)

# baseline card
c1 = card(s, MX, 1.92, 5.82, 3.78, shadow=True)
_, tf = tb(s, MX + 0.28, 2.14, 5.3, 0.35)
p = para(tf, first=True)
run(p, "BASELINE — THE MANUAL WAY", size=12, color=RED, bold=True, spc=1.6)
b1 = bullets(s, MX + 0.28, 2.62, 5.30, 2.9, [
    ("Hours of checking ", "— every paper copy marked by hand"),
    ("Results take days ", "— feedback arrives too late to act on"),
    ("No attempt history ", "— weak topics stay invisible"),
    ("Errors & duplicates ", "— totalling mistakes, repeat entries"),
    ("Nothing measured ", "— so teaching quality can't improve"),
], size=12.5, gap=10, marker="✗", marker_color=RED, marker_scale=0.95)
anim.fade(c1, delay=200)
anim.fade(b1, delay=320)

# arrow badge
badge = oval(s, 6.36, 3.42, 0.62, INDIGO)
set_gradient(badge)
btf = badge.text_frame
btf.margin_left = btf.margin_right = btf.margin_top = btf.margin_bottom = 0
bp = btf.paragraphs[0]
bp.alignment = PP_ALIGN.CENTER
run(bp, "→", size=22, color=WHITE, bold=True)
anim.fade(badge, delay=480)

# solution card
c2 = card(s, 6.94, 1.92, 5.82, 3.78, fill=CARD2, shadow=True)
_, tf = tb(s, 7.22, 2.14, 5.3, 0.35)
p = para(tf, first=True)
run(p, "WITH QUIZMASTER", size=12, color=GREEN, bold=True, spc=1.6)
b2 = bullets(s, 7.22, 2.62, 5.30, 2.9, [
    ("Graded in milliseconds ", "— automatically, on the server"),
    ("Instant feedback ", "— score, solutions & weak-topic insight"),
    ("Complete history ", "— every attempt, trend & leaderboard"),
    ("Validated, duplicate-safe data ", "with a full audit trail"),
    ("Quality tools built in ", "— defects, Pareto, FMEA, PDCA"),
], size=12.5, gap=10, marker="✓", marker_color=GREEN, marker_scale=1.0)
anim.fade(c2, delay=260)
anim.fade(b2, delay=380)

bar = card(s, MX, 5.94, CW, 0.74, line=None, radius=0.16)
set_gradient(bar, angle_deg=0)
_, tf = tb(s, MX, 5.94, CW, 0.74, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "From days of manual checking  →  results in milliseconds, "
       "with data you can actually improve on.",
    size=14.5, color=WHITE, bold=True)
anim.fade(bar, delay=620)
footer(s, 2)
anim.build()
notes(s, "Start with the baseline. In a typical classroom a quiz means "
         "paper, manual checking that takes hours, and results that reach "
         "students days later - too late to fix weak topics. There is no "
         "record of past attempts, marking errors and duplicate entries "
         "creep in, and with nothing measured, nothing can improve. "
         "QuizMaster removes each of these pain points one-to-one: instant "
         "grading, instant feedback, complete history, validated data and "
         "built-in quality tools.")

# =========================================================================== #
# SLIDE 3 - QUALITY OBJECTIVES + SRS SNAPSHOT                                 #
# =========================================================================== #
s = new_slide("bg_content.jpg", "fade")
anim = Animator(s)
anim.fade(*header(s, "Quality objectives · SRS snapshot",
                  [("Built around ", False),
                   ("20 measurable quality goals", True)],
                  "Every guideline goal (Q01–Q20) maps to a working, verifiable feature."),
          delay=0)

pillars = [
    ("Reliability & Accuracy", "Q01 · Q06 · Q07",
     "Auto-backups, audit log, strict validation, duplicate-entry guards."),
    ("Performance & Speed", "Q02 · Q05 · Q13 · Q17",
     "Indexed search, cached dashboards, pagination, compressed assets."),
    ("Usability & Accessibility", "Q03 · Q08 · Q12 · Q14",
     "Themes & palettes, dashboards, keyboard navigation, high contrast."),
    ("Security", "Q04",
     "Role-based portals, hashed passwords & OTPs, CSRF, rate limiting."),
    ("Reporting & Insight", "Q15 · Q20",
     "PDF / Excel / CSV exports, charts, date-range & printable reports."),
    ("Continuous Improvement", "Q09 · Q10 · Q11 · Q16 · Q18 · Q19",
     "Defect log, PDCA tracker, automated tests, docs & version log."),
]
pw, ph, gx, gy = 3.56, 1.26, 0.14, 0.14
for i, (title, qs, desc) in enumerate(pillars):
    x = MX + (i % 2) * (pw + gx)
    y = 1.98 + (i // 2) * (ph + gy)
    c = card(s, x, y, pw, ph, shadow=True)
    grad_bar(s, x + 0.18, y + 0.17, 0.34, 0.06)
    _, tf = tb(s, x + 0.62, y + 0.10, pw - 0.78, 0.3)
    p = para(tf, first=True)
    run(p, title, size=12.5, color=WHITE, bold=True)
    _, tf = tb(s, x + 0.18, y + 0.47, pw - 0.36, 0.25)
    p = para(tf, first=True)
    run(p, qs, size=9, color=CYAN_L, bold=True, spc=0.8)
    _, tf = tb(s, x + 0.18, y + 0.71, pw - 0.34, 0.52)
    p = para(tf, first=True, line=1.1)
    run(p, desc, size=10, color=MUTED)
    anim.fade(c, delay=180 + i * 90)

# SRS card
sx, sw = 8.02, 4.74
sc = card(s, sx, 1.98, sw, 4.06, fill=CARD2, shadow=True)
_, tf = tb(s, sx + 0.26, 2.16, sw - 0.5, 0.35)
p = para(tf, first=True)
run(p, "SRS SNAPSHOT", size=12, color=WHITE, bold=True, spc=1.6)
run(p, "   what the system must do", size=10.5, color=MUTED)
_, tf = tb(s, sx + 0.26, 2.56, sw - 0.5, 0.3)
p = para(tf, first=True)
run(p, "FUNCTIONAL", size=10, color=CYAN_L, bold=True, spc=1.8)
fb = bullets(s, sx + 0.26, 2.84, sw - 0.48, 1.75, [
    "Secure registration, login & role-based access",
    "Quiz & question-bank management (CRUD + import)",
    "Timed attempts with server-side auto-grading",
    "Results, history, analytics & report exports",
    "TQM tools, defect log & PDCA tracking",
    "Notifications, feedback & announcements",
], size=10.8, gap=5.5)
_, tf = tb(s, sx + 0.26, 4.62, sw - 0.5, 0.3)
p = para(tf, first=True)
run(p, "NON-FUNCTIONAL", size=10, color=CYAN_L, bold=True, spc=1.8)
nb = bullets(s, sx + 0.26, 4.90, sw - 0.48, 1.05, [
    "Responsive — mobile, tablet & desktop",
    "Fast — indexed queries, caching, pagination",
    "Safe — hashing, validation, backups, recovery",
], size=10.8, gap=5.5)
anim.fade(sc, delay=320)
anim.fade(fb, nb, delay=440)

strip = card(s, MX, 6.22, CW, 0.58, fill=CARD, radius=0.18)
_, tf = tb(s, MX, 6.22, CW, 0.58, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "Full traceability:  ", size=11.5, color=WHITE, bold=True)
run(p, "each Q-goal is mapped to its feature in code and reported live "
       "in the TQM centre.", size=11.5, color=BODY)
anim.fade(strip, delay=760)
footer(s, 3)
anim.build()
notes(s, "Quality was planned, not added later. We defined twenty quality "
         "goals - reliability, performance, usability, security, reporting "
         "and continuous improvement - and every single one maps to a "
         "feature that actually works in the app. On the right is the SRS "
         "in brief: what the system must do, and how well it must do it. "
         "Because the mapping lives in the code itself, an examiner can "
         "open the TQM centre and verify each goal live.")

# =========================================================================== #
# SLIDE 4 - SCOPE & USER ROLES                                                #
# =========================================================================== #
s = new_slide("bg_content.jpg", "wipe", "r")
anim = Animator(s)
anim.fade(*header(s, "Scope & user roles",
                  [("Two portals, ", False), ("one platform", True)],
                  "Built for institutes, coaching centres & self-learners — separate experiences for learning and managing."),
          delay=0)

roles = [
    (MX, "dash_banner.jpg", "Student Portal", "LEARN", [
        "OTP-verified sign-up & secure login",
        "Explore by subject, difficulty & search",
        "Timed attempts with autosave protection",
        "Instant results, streaks & recommendations",
        "Themes, profile & accessibility settings",
    ]),
    (6.94, "admin_banner.jpg", "Administrator Portal", "MANAGE", [
        "User, role & account-status management",
        "Quiz builder & question bank (CSV import)",
        "Results, analytics, audit & error logs",
        "Announcements, feedback & support inbox",
        "Backups, maintenance & system settings",
    ]),
]
for i, (x, img, title, tag, items) in enumerate(roles):
    c = card(s, x, 1.96, 5.82, 4.62, shadow=True)
    pic = s.shapes.add_picture(A(img), Inches(x + 0.16), Inches(2.12),
                               Inches(5.50), Inches(5.50 / 2.35))
    rounded_pic(pic, 3200)
    _, tf = tb(s, x + 0.26, 4.60, 3.9, 0.4)
    p = para(tf, first=True)
    run(p, title, size=16, color=WHITE, bold=True, font=HEAD)
    chip(s, x + 4.62, 4.62, 1.02, 0.32, tag, size=9, color=CYAN_L, bold=True)
    bl = bullets(s, x + 0.26, 5.06, 5.35, 1.45, items, size=11.3, gap=4.5)
    anim.fade(c, delay=200 + i * 140)
    anim.fade(pic, bl, delay=340 + i * 140)

_, tf = tb(s, MX, 6.72, CW, 0.3)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "One shared database, strict role-based access — students never "
       "see admin tools, admins never break a student's flow.",
    size=11, color=MUTED, italic=True)
footer(s, 4)
anim.build()
notes(s, "There are exactly two user roles. Students get a learning-focused "
         "portal: sign up with email OTP verification, explore quizzes, "
         "attempt them under a timer with autosave protection, and track "
         "their growth. Administrators get a complete management console: "
         "users, quizzes, the question bank, analytics, audit logs and "
         "system maintenance. Both portals share one database, but access "
         "is strictly separated by role - that separation is itself one of "
         "our security quality goals.")

# =========================================================================== #
# SLIDE 5 - MODULES & FEATURES                                                #
# =========================================================================== #
s = new_slide("bg_accent.jpg", "cover", "l")
anim = Animator(s)
anim.fade(*header(s, "Modules & features",
                  [("Seven modules. ", False), ("One seamless system.", True)],
                  "Each module is a self-contained unit with its own routes and services — easy to test, easy to extend."),
          delay=0)

modules = [
    ("Auth & Security", "Email-OTP verification, password reset, role-based access, CSRF & rate limiting."),
    ("Student Portal", "Personal dashboard, explore, calendar, leaderboard, streaks & recommendations."),
    ("Quiz Engine", "Timed player with shuffled questions, autosave, auto-submit & instant grading."),
    ("Question Bank", "Categories & difficulty levels, CSV / JSON bulk import, live duplicate warning."),
    ("Admin Portal", "Users & quizzes, announcements, audit trail, error log, backups & settings."),
    ("Analytics & Reports", "Score trends & charts, per-quiz analysis, one-click PDF / Excel / CSV exports."),
    ("TQM Workspace", "Defect log, Pareto, Fishbone, FMEA, PDCA, SIPOC–CTQ & statistical control charts."),
]
cw_, ch_, gx = 2.95, 1.98, 0.13
positions = [(MX + i * (cw_ + gx), 1.98) for i in range(4)] + \
            [(MX + 0.5 * (cw_ + gx) + i * (cw_ + gx), 4.10) for i in range(3)]
for i, ((title, desc), (x, y)) in enumerate(zip(modules, positions)):
    c = card(s, x, y, cw_, ch_, shadow=True)
    tile = card(s, x + 0.17, y + 0.17, 0.48, 0.48, line=None, radius=0.28)
    set_gradient(tile)
    ttf = tile.text_frame
    ttf.margin_left = ttf.margin_right = ttf.margin_top = ttf.margin_bottom = 0
    ttf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tp = ttf.paragraphs[0]
    tp.alignment = PP_ALIGN.CENTER
    run(tp, f"{i + 1:02d}", size=14, color=WHITE, bold=True, font=HEAD)
    _, tf = tb(s, x + 0.78, y + 0.17, cw_ - 0.92, 0.55, anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, first=True, line=1.05)
    run(p, title, size=13, color=WHITE, bold=True)
    _, tf = tb(s, x + 0.17, y + 0.80, cw_ - 0.34, 1.08)
    p = para(tf, first=True, line=1.16)
    run(p, desc, size=10.5, color=MUTED)
    anim.fade(c, delay=170 + i * 80)

strip = card(s, MX, 6.28, CW, 0.56, fill=CARD, radius=0.2)
_, tf = tb(s, MX, 6.28, CW, 0.56, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "TECH STACK    ", size=10.5, color=CYAN_L, bold=True, spc=1.5)
run(p, "Python · Flask · SQLAlchemy · SQLite · Jinja2 · Matplotlib · "
       "fpdf2 · openpyxl · pytest", size=12, color=WHITE, bold=True)
anim.fade(strip, delay=780)
footer(s, 5)
anim.build()
notes(s, "Functionally the system is seven modules. Security first: OTP "
         "verification and role-based access. Then the learning side - "
         "student portal and the quiz engine with its timer, autosave and "
         "instant grading. The question bank lets admins build content "
         "quickly, including bulk import. Analytics turns attempts into "
         "insight and exportable reports. And the seventh module, the TQM "
         "workspace, is what makes this project different - quality tools "
         "running inside the product itself.")

# =========================================================================== #
# SLIDE 6 - SYSTEM & DATABASE DESIGN (+ modular folders)                      #
# =========================================================================== #
s = new_slide("bg_content.jpg", "fade")
anim = Animator(s)
anim.fade(*header(s, "System & database design",
                  [("Clean, ", False), ("modular architecture", True)],
                  "Routes, services, models and templates each live in their own layer — nothing is tangled."),
          delay=0)

def section_label(x, y, text):
    _, tf = tb(s, x, y, 3.2, 0.3)
    p = para(tf, first=True)
    run(p, text, size=11, color=CYAN_L, bold=True, spc=1.8)

# --- left: layers
section_label(MX, 1.94, "LAYERED DESIGN")
layers = [
    ("Presentation", "79 Jinja2 templates · responsive CSS · vanilla JS"),
    ("Routing", "7 Flask blueprints · 110+ routes"),
    ("Business Services", "12 services — grading, attempts, exports, charts, email, backup"),
    ("Data Layer", "SQLAlchemy ORM · SQLite · Alembic migrations"),
]
ly = 2.30
for i, (name, det) in enumerate(layers):
    c = card(s, MX, ly, 4.42, 0.88, fill=CARD if i % 2 == 0 else CARD2,
             shadow=True)
    grad_bar(s, MX + 0.16, ly + 0.18, 0.07, 0.52, angle=90)
    _, tf = tb(s, MX + 0.40, ly + 0.13, 3.95, 0.32)
    p = para(tf, first=True)
    run(p, name, size=13, color=WHITE, bold=True)
    _, tf = tb(s, MX + 0.40, ly + 0.45, 3.95, 0.38)
    p = para(tf, first=True, line=1.08)
    run(p, det, size=9.8, color=MUTED)
    anim.fade(c, delay=180 + i * 110)
    if i < 3:
        ar = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(MX + 2.08),
                                Inches(ly + 0.90), Inches(0.26), Inches(0.20))
        ar.fill.solid(); ar.fill.fore_color.rgb = VIOLET
        ar.line.fill.background(); ar.shadow.inherit = False
    ly += 1.12

# --- middle: database groups
section_label(5.32, 1.94, "DATABASE · 22 TABLES")
groups = [
    ("Users & Access", "User · EmailOTP · PasswordResetToken"),
    ("Quiz Core", "Quiz · Question · AnswerOption · Category · QuizAttempt · AttemptAnswer"),
    ("Quality (TQM)", "Defect · FMEAItem · PDCAAction · ChangelogEntry"),
    ("System", "AuditLog · Notification · Feedback · Announcement · ErrorLog · Setting"),
]
gy = 2.30
for i, (name, tables) in enumerate(groups):
    c = card(s, 5.32, gy, 3.94, 0.97, shadow=True)
    _, tf = tb(s, 5.54, gy + 0.11, 3.55, 0.3)
    p = para(tf, first=True)
    run(p, name, size=12, color=WHITE, bold=True)
    _, tf = tb(s, 5.54, gy + 0.42, 3.58, 0.5)
    p = para(tf, first=True, line=1.12)
    run(p, tables, size=9.3, color=IND_L, font=MONO)
    anim.fade(c, delay=260 + i * 110)
    gy += 1.09

# --- right: folder architecture
section_label(9.54, 1.94, "MODULAR FOLDERS")
fc = card(s, 9.54, 2.30, 3.22, 4.24, fill=FRAMEBG, shadow=True)
tree = [
    "QuizMaster/",
    "├─ backend/",
    "│  ├─ blueprints/ (7)",
    "│  ├─ models/ (4)",
    "│  └─ services/ (12)",
    "├─ frontend/",
    "│  ├─ templates/ (79)",
    "│  └─ static/ css·js",
    "├─ database/",
    "│  └─ migrations/",
    "├─ tests/ (pytest)",
    "├─ docs/ · tqm/",
    "└─ app.py · wsgi.py",
]
_, tf = tb(s, 9.76, 2.50, 2.9, 3.3)
for i, line_txt in enumerate(tree):
    p = para(tf, first=(i == 0), line=1.28)
    col = WHITE if i == 0 else (CYAN_L if line_txt.startswith(("├─ b", "├─ f", "├─ d", "├─ t")) else BODY)
    run(p, line_txt, size=10.3, color=col, font=MONO, bold=(i == 0))
_, tf = tb(s, 9.76, 5.92, 2.82, 0.55)
p = para(tf, first=True, line=1.12)
run(p, "New feature = new blueprint + service. Nothing else changes.",
    size=9.5, color=MUTED, italic=True)
anim.fade(fc, delay=340)
footer(s, 6)
anim.build()
notes(s, "Architecturally, requests flow through four clean layers: "
         "templates render the pages, seven blueprints route requests, "
         "twelve services hold the business logic like grading and exports, "
         "and SQLAlchemy models talk to the database. The 22 tables fall "
         "into four domains - users, quiz core, quality and system. And "
         "the folder structure mirrors the architecture exactly, so any "
         "developer can find any feature in seconds. This modularity is "
         "our maintainability quality goal, Q11, in practice.")

# =========================================================================== #
# SLIDE 7 - MAIN SYSTEM WORKFLOW                                              #
# =========================================================================== #
s = new_slide("bg_accent.jpg", "push", "l")
anim = Animator(s)
anim.fade(*header(s, "Main system workflow",
                  [("From sign-up to insight in ", False), ("six steps", True)],
                  "Designed so answers are never lost — and results need zero manual work."),
          delay=0)

steps = [
    ("1 · Register", "email OTP verified"),
    ("2 · Explore", "pick a quiz"),
    ("3 · Attempt", "timer + autosave"),
    ("4 · Submit", "instant grading"),
    ("5 · Review", "results & history"),
    ("6 · Improve", "analytics → PDCA"),
]
sw_, overlap = 2.12, 0.14
x = (SLIDE_W - (6 * sw_ - 5 * overlap)) / 2
for i, (t1, t2) in enumerate(steps):
    shape_type = MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON
    sh = s.shapes.add_shape(shape_type, Inches(x), Inches(2.02),
                            Inches(sw_), Inches(0.82))
    sh.line.color.rgb = RGBColor(0x0B, 0x0B, 0x24) if False else INDIGO
    sh.line.width = Pt(0.75)
    sh.shadow.inherit = False
    set_gradient(sh, angle_deg=0)
    set_shadow(sh, blur=0.07, dist=0.04, alpha=40)
    tfr = sh.text_frame
    tfr.word_wrap = False
    tfr.margin_left = Inches(0.34 if i else 0.16)
    tfr.margin_right = Inches(0.05)
    tfr.margin_top = tfr.margin_bottom = Inches(0.02)
    tfr.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tfr.paragraphs[0]
    run(p, t1, size=13, color=WHITE, bold=True, font=HEAD)
    p = para(tfr, line=1.0)
    run(p, t2, size=9, color=RGBColor(0xE3, 0xE5, 0xFF))
    anim.fade(sh, delay=160 + i * 110)
    x += sw_ - overlap

_, tf = tb(s, MX, 2.94, CW, 0.28)
p = para(tf, first=True, align=PP_ALIGN.RIGHT)
run(p, "Step 6 feeds improvements back into better quizzes — a continuous "
       "PDCA loop.", size=10.5, color=MUTED, italic=True)

shots = [("login.jpg", "Secure sign-in"), ("explore.jpg", "Explore quizzes"),
         ("quiz_player.jpg", "Focused quiz player"),
         ("results.jpg", "Instant results")]
bw = 2.95
for i, (img, cap) in enumerate(shots):
    bx = MX + i * (bw + 0.13)
    shps, th = browser(s, A(img), bx, 3.30, bw, ratio=1.60,
                       url="quizmaster.app", bar_h=0.28)
    anim.fade(*shps, delay=300 + i * 120)
    _, tf = tb(s, bx, 3.30 + th + 0.09, bw, 0.3)
    p = para(tf, first=True, align=PP_ALIGN.CENTER)
    run(p, cap, size=11, color=BODY, bold=True)

safety = ["✓  Answers autosave as you type",
          "✓  Auto-submits when time runs out",
          "✓  Refresh or disconnect? Resume safely"]
for i, txt in enumerate(safety):
    c = card(s, MX + i * (3.98 + 0.125), 6.08, 3.98, 0.52, fill=CARD,
             radius=0.22)
    _, tf = tb(s, MX + i * (3.98 + 0.125), 6.08, 3.98, 0.52,
               anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, first=True, align=PP_ALIGN.CENTER)
    run(p, txt, size=11.5, color=WHITE, bold=True)
    anim.fade(c, delay=700 + i * 90)
footer(s, 7)
anim.build()
notes(s, "Here is the main workflow end to end. A student registers and "
         "verifies an email OTP, explores and picks a quiz, attempts it "
         "under a timer, and submits. Grading happens on the server "
         "immediately - no teacher action needed. The student reviews the "
         "result, and the data flows into admin analytics, which feeds the "
         "PDCA improvement cycle. Notice the three safety nets: answers "
         "autosave continuously, the quiz auto-submits at the deadline, "
         "and even a refresh or disconnect cannot lose an attempt. That "
         "is reliability, goal Q01, in action.")

# =========================================================================== #
# SLIDE 8 - CRUD & DATABASE INTEGRATION                                       #
# =========================================================================== #
s = new_slide("bg_content.jpg", "wipe", "r")
anim = Animator(s)
anim.fade(*header(s, "CRUD operations · Database integration",
                  [("Full CRUD, ", False), ("fully integrated", True)],
                  "Every record is created, read, updated and deleted through validated, audited workflows."),
          delay=0)

crud = [
    ("C", "Create", "Quizzes, questions, users, categories, announcements — plus bulk CSV / JSON import."),
    ("R", "Read", "Live search, filters, sorting & pagination on every list and dashboard."),
    ("U", "Update", "Edit content, toggle publish state, manage roles & account status."),
    ("D", "Delete", "Confirmation dialog first — every deletion is written to the audit log."),
]
cy = 1.98
for i, (letter, name, desc) in enumerate(crud):
    c = card(s, MX, cy, 5.28, 1.02, shadow=True)
    tile = card(s, MX + 0.17, cy + 0.20, 0.62, 0.62, line=None, radius=0.26)
    set_gradient(tile)
    ttf = tile.text_frame
    ttf.margin_left = ttf.margin_right = ttf.margin_top = ttf.margin_bottom = 0
    ttf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tp = ttf.paragraphs[0]
    tp.alignment = PP_ALIGN.CENTER
    run(tp, letter, size=21, color=WHITE, bold=True, font=HEAD)
    _, tf = tb(s, MX + 0.98, cy + 0.13, 4.15, 0.32)
    p = para(tf, first=True)
    run(p, name, size=14, color=WHITE, bold=True)
    _, tf = tb(s, MX + 0.98, cy + 0.47, 4.15, 0.52)
    p = para(tf, first=True, line=1.12)
    run(p, desc, size=10.3, color=MUTED)
    anim.fade(c, delay=180 + i * 110)
    cy += 1.16

bshapes, _ = browser(s, A("admin_quizzes.jpg"), 6.22, 1.98, 6.54, ratio=1.60,
                     url="quizmaster.app/admin/quizzes")
anim.fade(*bshapes, delay=320)
qshapes, _ = browser(s, A("question_bank.jpg"), 5.98, 4.12, 3.42, ratio=1.60,
                     url="quizmaster.app/admin/questions", bar_h=0.28)
anim.fade(*qshapes, delay=560)

strip = card(s, MX, 6.62, CW, 0.42, fill=CARD, radius=0.24)
_, tf = tb(s, MX, 6.62, CW, 0.42, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "SQLAlchemy ORM · Alembic migrations · unique constraints block "
       "duplicates · append-only audit log · automatic backups",
    size=10.8, color=BODY)
anim.fade(strip, delay=740)
footer(s, 8)
anim.build()
notes(s, "All data operations are proper CRUD, integrated end to end with "
         "the database. Admins create quizzes and questions - or import "
         "them in bulk from CSV or JSON. Every list supports search, "
         "filters, sorting and pagination. Updates cover everything from "
         "editing a question to changing a user's account status. Deletes "
         "always ask for confirmation and are written to an append-only "
         "audit log. Under the hood, SQLAlchemy ORM prevents SQL "
         "injection, and unique constraints make duplicate entries - "
         "quality goal Q06 - impossible at the database level.")

# =========================================================================== #
# SLIDE 9 - WORKING APPLICATION: STUDENT EXPERIENCE                           #
# =========================================================================== #
s = new_slide("bg_content.jpg", "fade")
anim = Animator(s)
anim.fade(*header(s, "Product tour · Student side",
                  [("A dashboard that ", False), ("coaches every student", True)],
                  "The working application — real screens from the live system."),
          delay=0)

bshapes, th = browser(s, A("dashboard.jpg"), MX, 1.98, 6.52, ratio=1.48,
                      url="quizmaster.app/dashboard")
anim.fade(*bshapes, delay=220)
_, tf = tb(s, MX, 1.98 + th + 0.08, 6.52, 0.3)
p = para(tf, first=True, align=PP_ALIGN.CENTER)
run(p, "Student dashboard — live scores, trends & recommendations",
    size=11, color=BODY, bold=True)

rx, rw = 7.38, 5.38
bl = bullets(s, rx, 2.02, rw, 2.3, [
    ("Personal dashboard ", "— streaks, score trend, subject strengths"),
    ("Focused quiz player ", "— live timer, progress, keyboard control"),
    ("Instant review ", "— correct answers with explanations"),
    ("Smart recommendations ", "target your weakest subjects"),
    ("Made personal ", "— light/dark themes, 4 palettes, accessibility"),
], size=12.3, gap=8)
anim.fade(bl, delay=360)

minis = [("quiz_player.jpg", "Timed quiz player"),
         ("results.jpg", "Result & answer review")]
mw = (rw - 0.14) / 2
for i, (img, cap) in enumerate(minis):
    bx = rx + i * (mw + 0.14)
    shps, mth = browser(s, A(img), bx, 4.42, mw, ratio=1.60,
                        url="quizmaster.app", bar_h=0.26)
    anim.fade(*shps, delay=500 + i * 130)
    _, tf = tb(s, bx, 4.42 + mth + 0.07, mw, 0.28)
    p = para(tf, first=True, align=PP_ALIGN.CENTER)
    run(p, cap, size=10.5, color=BODY, bold=True)
footer(s, 9)
anim.build()
notes(s, "This is the live student experience. The dashboard acts like a "
         "coach: it shows the study streak, a score-trend graph, subject-"
         "wise performance, and it recommends quizzes in the student's "
         "weakest subjects - here, Mathematics. During a quiz the player "
         "shows the timer and progress and supports keyboard answering. "
         "The moment a quiz is submitted, the student sees the score and "
         "can review every answer with explanations. Themes, colour "
         "palettes and accessibility settings make it personal - quality "
         "goals Q03, Q08 and Q12.")

# =========================================================================== #
# SLIDE 10 - TQM QUALITY WORKSPACE                                            #
# =========================================================================== #
s = new_slide("bg_accent.jpg", "cover", "l")
anim = Animator(s)
anim.fade(*header(s, "TQM quality workspace",
                  [("Quality isn't a chapter — ", False), ("it's built in", True)],
                  "A complete Total Quality Management centre, running on this project's own real defect data."),
          delay=0)

bl = bullets(s, MX, 2.00, 5.15, 3.1, [
    ("Defect log ", "— 16 real development defects, 100% closed"),
    ("Pareto analysis ", "— the vital few causes behind ~80% of defects"),
    ("Fishbone diagram ", "— root causes across six categories"),
    ("FMEA ", "— 12 risks scored by RPN, re-scored after action"),
    ("PDCA · SIPOC · CTQ ", "— the quiz process, mapped end-to-end"),
    ("Control charts ", "— submission latency under statistical control"),
], size=12.3, gap=9)
anim.fade(bl, delay=200)

ctq = [("7.39 ms", "P95 submission processing\n(target < 500 ms)"),
       ("100%", "autosave success &\ngrading reproducibility")]
for i, (num, lab) in enumerate(ctq):
    x = MX + i * (2.56 + 0.14)
    c = card(s, x, 5.14, 2.56, 1.06, fill=CARD2, shadow=True)
    _, tf = tb(s, x + 0.2, 5.27, 2.25, 0.5)
    p = para(tf, first=True)
    run(p, num, size=21, color=WHITE, bold=True, font=HEAD, gradient=True)
    _, tf = tb(s, x + 0.2, 5.74, 2.25, 0.44)
    p = para(tf, first=True, line=1.1)
    run(p, lab, size=9.3, color=MUTED)
    anim.fade(c, delay=480 + i * 120)

_, tf = tb(s, MX, 6.36, 5.3, 0.32)
p = para(tf, first=True)
run(p, "Nothing is simulated — every figure is computed live.", size=11,
    color=CYAN_L, italic=True, bold=True)

bshapes, _ = browser(s, A("tqm_overview.jpg"), 6.02, 1.98, 5.42, ratio=1.35,
                     url="quizmaster.app/admin/tqm")
anim.fade(*bshapes, delay=320)
pshapes, _ = browser(s, A("pareto.jpg"), 9.28, 3.92, 3.32, ratio=1.35,
                     url="quizmaster.app/admin/tqm/pareto", bar_h=0.28)
anim.fade(*pshapes, delay=580)
footer(s, 10)
anim.build()
notes(s, "This is the heart of the project. The TQM centre applies the "
         "classic quality tools to QuizMaster itself. Sixteen genuine "
         "defects found during development are logged and root-caused - "
         "all closed. Pareto analysis shows UI/layout, authentication and "
         "validation are the vital-few categories. FMEA scores twelve "
         "risks by RPN and re-scores them after corrective action. PDCA, "
         "SIPOC-CTQ and control charts complete the cycle. And look at "
         "the live CTQ metrics: submissions process in about 7 "
         "milliseconds against a 500-millisecond target, with 100 percent "
         "autosave success and perfectly reproducible grading.")

# =========================================================================== #
# SLIDE 11 - OUTCOMES, TESTING, ROADMAP & THANK YOU                           #
# =========================================================================== #
s = new_slide("bg_cover.jpg", "fade")
anim = Animator(s)
anim.fade(*header(s, "Outcomes · Testing · Roadmap",
                  [("Results that ", False), ("speak for themselves", True)],
                  None), delay=0)

tiles = [("13,000+", "lines of code"), ("110+", "routes · 7 blueprints"),
         ("22", "database tables"), ("50+", "automated tests"),
         ("16 → 0", "defects logged → open")]
tw = (CW - 4 * 0.12) / 5
for i, (num, lab) in enumerate(tiles):
    x = MX + i * (tw + 0.12)
    c = card(s, x, 1.62, tw, 1.18, shadow=True)
    _, tf = tb(s, x, 1.82, tw, 0.55)
    p = para(tf, first=True, align=PP_ALIGN.CENTER)
    run(p, num, size=23, color=WHITE, bold=True, font=HEAD, gradient=True)
    _, tf = tb(s, x, 2.38, tw, 0.3)
    p = para(tf, first=True, align=PP_ALIGN.CENTER)
    run(p, lab, size=10, color=MUTED)
    anim.fade(c, delay=160 + i * 90)

cards = [
    (MX, "QUALITY, VERIFIED", [
        ("pytest suite ", "— auth, quiz flow, grading security, TQM tools"),
        ("Render checks ", "catch template errors before users do"),
        ("Every real defect ", "logged, root-caused & fixed (100% closure)"),
        ("Security by design ", "— scrypt hashing, CSRF, rate limiting"),
    ]),
    (6.80, "THE ROAD AHEAD", [
        ("Richer assessments ", "— more question types & formats"),
        ("Deeper analytics ", "— more detailed quality reporting"),
        ("CI / CD pipeline ", "with broader automated test coverage"),
        ("Scales further ", "— database optimisation & monitoring"),
    ]),
]
for j, (x, title, items) in enumerate(cards):
    c = card(s, x, 3.12, 5.96, 2.42, fill=CARD if j == 0 else CARD2,
             shadow=True)
    grad_bar(s, x + 0.26, 3.34, 0.4, 0.065)
    _, tf = tb(s, x + 0.78, 3.22, 4.9, 0.32)
    p = para(tf, first=True)
    run(p, title, size=12.5, color=WHITE, bold=True, spc=1.4)
    bl = bullets(s, x + 0.26, 3.68, 5.45, 1.75, items, size=11.8, gap=8)
    anim.fade(c, delay=320 + j * 150)
    anim.fade(bl, delay=440 + j * 150)

band = card(s, MX, 5.86, CW, 1.02, line=None, radius=0.14)
set_gradient(band, angle_deg=0)
set_shadow(band, blur=0.12, dist=0.05, alpha=45)
s.shapes.add_picture(A("logo.png"), Inches(MX + 0.3), Inches(6.08),
                     Inches(0.58), Inches(0.58))
_, tf = tb(s, MX + 1.08, 5.86, 6.6, 1.02, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, line=1.05)
run(p, "Thank you!", size=21, color=WHITE, bold=True, font=HEAD)
run(p, "   Questions & a live demo are most welcome.", size=12.5,
    color=RGBColor(0xE8, 0xEA, 0xFF))
_, tf = tb(s, 8.2, 5.86, 4.36, 1.02, anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, first=True, align=PP_ALIGN.RIGHT, line=1.15)
run(p, "Ashish", size=12.5, color=WHITE, bold=True)
p = para(tf, align=PP_ALIGN.RIGHT, line=1.15)
run(p, "github.com/Ashishdumka24/QuizMaster", size=10.5,
    color=RGBColor(0xDD, 0xE0, 0xFF))
anim.fade(band, delay=680)
footer(s, 11)
anim.build()
notes(s, "To close: QuizMaster is a complete, tested, working system - "
         "over thirteen thousand lines of code, more than a hundred "
         "routes, twenty-two tables, and a pytest suite covering "
         "authentication, the quiz flow, grading security and the quality "
         "tools. All sixteen real defects we found are fixed and "
         "documented. Next steps are richer question types, deeper "
         "analytics, CI/CD and further scaling. Thank you for your time - "
         "I am happy to take questions, and even happier to give a live "
         "demo.")

# --------------------------------------------------------------------------- #
cp = prs.core_properties
cp.title = "QuizMaster — Online Quiz, Assessment & TQM Quality Platform"
cp.author = "Ashish"
cp.subject = "BBAT104 Fundamentals of TQM — Project Presentation"
cp.comments = ("Learn Smarter · Assess Better · Improve Continuously. "
               "11-slide deck with presenter notes; manual slide advance.")

prs.save(OUT)
print(f"Saved: {OUT}")
print(f"Slides: {len(prs.slides.__iter__.__self__._sldIdLst)}")
