"""Quality goals Q01–Q20 exactly as listed in the BBAT104 project guidelines (session 2026–27),
with where each suggested feature is implemented in QuizMaster."""

QUALITY_GOALS = [
    {
        "code": "Q01",
        "goal": "Improve Reliability",
        "suggested": "Auto Backup, Audit Log, Input Validation, Error Recovery, User Roles",
        "implemented": "Automatic + manual SQLite backups; append-only audit log; server-side validation on every form; autosave + local answer backup + auto-submit at deadline (error recovery); student/admin roles stored in DB"
    },
    {
        "code": "Q02",
        "goal": "Improve Performance",
        "suggested": "Fast Search, Optimized Reports, Dashboard, CSV Import, Efficient DB Queries",
        "implemented": "Indexed search on quizzes/questions/users; aggregate SQL for reports; live dashboards; CSV/JSON question import; grouped queries + pagination"
    },
    {
        "code": "Q03",
        "goal": "Improve Usability",
        "suggested": "Dark Mode, Custom Themes, Dashboard Overview, Search Filters, Calendar",
        "implemented": "Light/dark/system theme; 4 colour palettes; student & admin dashboards; filters on every list; quiz calendar"
    },
    {
        "code": "Q04",
        "goal": "Improve Security",
        "suggested": "Role-Based Login, Password Reset, Input Validation, Audit Trail, Encryption",
        "implemented": "Separate student/admin portals with DB roles; hashed single-use reset tokens; validation; audit trail; password hashing (Werkzeug scrypt), HMAC-SHA256-hashed OTPs and reset tokens, HTTPS/secure cookies in production"
    },
    {
        "code": "Q05",
        "goal": "Reduce Response Time",
        "suggested": "Fast Search, Quick Navigation, Cached Dashboard, DB Indexing, Paginated Reports",
        "implemented": "Search suggestions; sidebar + keyboard shortcuts; cached admin overview; indexed columns; paginated tables"
    },
    {
        "code": "Q06",
        "goal": "Reduce Duplicate Entries",
        "suggested": "Unique ID Constraints, Pre-add Validation, Search Before Add, Confirmation Dialogs",
        "implemented": "Unique email/slug/code constraints; duplicate quiz-title check; live similar-question search while typing; confirm dialogs; idempotent submit"
    },
    {
        "code": "Q07",
        "goal": "Improve Data Accuracy",
        "suggested": "Input Masking, Dropdown Lists, Auto-Complete, Confirmation Modals, Audit Logs",
        "implemented": "OTP digit-only input, number/date inputs with bounds; dropdowns for every enumerated field; quiz search auto-complete; confirmation modals; audit logs"
    },
    {
        "code": "Q08",
        "goal": "Improve User Satisfaction",
        "suggested": "Interactive Dashboard, Visual Reports, Theme Toggle, Shortcuts, User Profile Settings",
        "implemented": "Interactive SVG charts with tooltips; visual result review; theme toggle; keyboard shortcuts page; profile photo, preferences"
    },
    {
        "code": "Q09",
        "goal": "Reduce Bugs",
        "suggested": "Exception Handling, Strict Validation, Module Tests, Bug Tracker, Error Logs",
        "implemented": "Global error handlers; strict validation; pytest suite; in-app defect tracker; error log with convert-to-defect"
    },
    {
        "code": "Q10",
        "goal": "Improve Documentation",
        "suggested": "Interactive README, User Manual, Help/FAQ Screen, About Page, Inline Code Comments",
        "implemented": "README with screenshots; in-app + Markdown user manual; Help/FAQ page; About page; docstrings/comments"
    },
    {
        "code": "Q11",
        "goal": "Improve Maintainability",
        "suggested": "Modular Structure, Config Files, System Settings, Activity Logs, Code Comments",
        "implemented": "Blueprints/services/models packages; config.py + .env; admin System Settings; activity/audit logs; comments"
    },
    {
        "code": "Q12",
        "goal": "Improve Accessibility",
        "suggested": "High Contrast, Font Resizing, Keyboard Navigation, Dark Mode, Minimalist Layout",
        "implemented": "High-contrast mode; font-size slider; keyboard navigation incl. quiz player keys, skip link, focus rings; dark mode; clean layouts; reduced motion"
    },
    {
        "code": "Q13",
        "goal": "Faster Search & Retrieval",
        "suggested": "Search Filters, Sorting Options, Dashboard Quick-Search, DB Query Optimization",
        "implemented": "Filters; sort options on explore/users; top-bar quick search; indexed/grouped queries"
    },
    {
        "code": "Q14",
        "goal": "Improve Navigation",
        "suggested": "Breadcrumb Trails, Top Navigation Bar, Shortcuts, Dashboard Tiles, Home Button",
        "implemented": "Breadcrumbs; top bar; shortcuts; quick-link tiles; role-aware clickable logo (home)"
    },
    {
        "code": "Q15",
        "goal": "Better Reporting",
        "suggested": "PDF Export, Excel Export, Graphical Charts, Date Range Filters, Printable Layouts",
        "implemented": "PDF (fpdf2) and Excel (openpyxl) exports; charts; date-range filters on results/analytics/audit; print stylesheet & printable TQM report"
    },
    {
        "code": "Q16",
        "goal": "Improve Testing",
        "suggested": "Unit Test Cases, Bug Log Matrix, Input Bounds Testing, System Logs",
        "implemented": "pytest unit/integration tests; defect log + check sheet matrix; bounds tests on numeric inputs; rotating log file + request metrics"
    },
    {
        "code": "Q17",
        "goal": "Reduce Memory Usage",
        "suggested": "Asset Compression, On-Demand Data Loading, DB Purge Tools, Query Caching",
        "implemented": "response compression via Flask-Compress; pagination and lazy images; maintenance purge tools; in-process TTL cache for stats"
    },
    {
        "code": "Q18",
        "goal": "Improve Error Handling",
        "suggested": "Standardized Exception Catching, Friendly UI Alerts, System Error Logs, Recovery",
        "implemented": "Central error handlers + JSON error envelope; toasts and friendly error pages; error log; autosave/offline retry recovery"
    },
    {
        "code": "Q19",
        "goal": "Continuous Improvement (PDCA)",
        "suggested": "In-App Feedback Form, Bug Report Form, Version Log, PDCA Action Tracker",
        "implemented": "Feedback ratings; bug report form → defect log; version log; PDCA tracker"
    },
    {
        "code": "Q20",
        "goal": "Overall Software Quality",
        "suggested": "Balanced Mix of Dashboard, Validation, Export Reports, Backups, and Role Controls",
        "implemented": "All of the above"
    }
]
