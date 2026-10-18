# 🚀 QuizMaster — Online Quiz, Assessment & TQM Quality Platform

**Learn Smarter · Assess Better · Improve Continuously**

QuizMaster is a Flask-powered online quiz and assessment platform featuring dedicated student and administrator portals, quiz management, performance reporting, and a Total Quality Management (TQM) workspace.

Designed as a general-purpose assessment platform, QuizMaster combines interactive quizzes with quality analysis, performance measurement, and continuous-improvement concepts.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Application Architecture](#application-architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation and Setup](#installation-and-setup)
- [Environment Configuration](#environment-configuration)
- [Database Management](#database-management)
- [Useful Commands](#useful-commands)
- [Testing](#testing)
- [Total Quality Management (TQM)](#total-quality-management-tqm)
- [Security](#security)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)
- [Academic Context](#academic-context)
- [License](#license)
- [Author](#author)

---

## 📖 Overview

**QuizMaster** is a responsive web application designed to simplify online assessments, quiz participation, result evaluation, and performance tracking.

The application provides separate experiences for students and administrators. Students can explore quizzes, participate in assessments, review their results, and track their progress. Administrators can manage users, quizzes, questions, and assessment reports through a dedicated management interface.

The project also includes a dedicated TQM workspace that connects software quality objectives with practical quality-management tools, defect analysis, and continuous-improvement activities.

QuizMaster was developed in the context of the **BBAT104 Fundamental of TQM** course project, with an emphasis on structured workflows, measurable performance, data quality, and user experience.

### Project Vision

To create a reliable, accessible, and quality-focused online assessment platform that makes learning and evaluation more organized, measurable, and effective.

---

## ✨ Key Features

### 👨‍🎓 Student Portal

- Student registration and authentication.
- Student dashboard and quiz discovery.
- Quiz details and interactive quiz participation.
- Answer submission and automated grading workflows.
- Score calculation and result review.
- Quiz attempt history.
- Account profile and personal preferences.
- Profile-photo management.
- Notifications and feedback functionality.
- Theme and accessibility-related preferences.

### 🛡️ Authentication and Account Security

- Login and registration workflows.
- Role-based access for students and administrators.
- Email OTP verification and password-reset workflows.
- Password hashing and token-handling utilities.
- Session management and account security controls.
- Input validation and protection for sensitive operations.
- Account-status management.

Real email delivery requires valid SMTP configuration. Authentication and account-recovery workflows should be tested in the configured environment before production use.

### 🧑‍💼 Administrator Portal

- Dedicated administrator dashboard.
- User and account management.
- Quiz creation and management.
- Question-bank management.
- Question import support for applicable CSV and JSON workflows.
- Quiz-result monitoring.
- Performance statistics and analytics.
- Administrative settings.
- Audit and activity information.
- Defect-management and quality-reporting functionality.
- Supported backup and maintenance operations.

### 📝 Quiz and Assessment System

- Structured quiz and question management.
- Quiz participation and answer submission.
- Server-side answer validation and grading.
- Assessment attempt and result records.
- Quiz history and result review.
- Search, filtering, sorting, and pagination where supported.
- Attempt-recovery features documented in the application.
- Quiz-related reporting and data exports.

### 📊 Reporting and Analytics

QuizMaster includes reporting-related functionality intended to help administrators review assessment and quality information.

Supported reporting components include:

- Assessment result summaries.
- Performance statistics.
- Quiz and user-related reports.
- CSV exports.
- Excel exports.
- PDF reports.
- Quality-analysis charts and reports.

Export availability depends on the relevant report implementation and configuration.

### 📈 TQM Quality Workspace

The TQM workspace connects quality-management concepts with the application through quality objectives, defect records, analytical tools, and reporting.

It includes functionality associated with:

- Quality-goal mapping.
- Defect logging and analysis.
- Pareto analysis.
- Fishbone or cause-and-effect analysis.
- Failure Mode and Effects Analysis (FMEA).
- Plan–Do–Check–Act (PDCA).
- SIPOC and Critical-to-Quality (CTQ) analysis.
- Statistical quality-control charts.
- TQM reporting and continuous-improvement tracking.

The project's quality-objective mapping is maintained in `backend/quality_goals.py`.

### 🎨 User Experience

- Browser-based interface.
- Dedicated student and administrator areas.
- Responsive page layouts.
- Light, dark, and system theme options where supported.
- Colour and accessibility-related preferences.
- Interactive navigation and dashboard components.
- User profile and account settings.
- Mobile, tablet, and desktop layout support.

---

## 🧰 Technology Stack

QuizMaster uses a Python-based backend and a browser-based frontend.

| Technology | Purpose |
|---|---|
| Python | Backend application logic |
| Flask | Web framework and application routing |
| HTML5 | Webpage structure |
| CSS3 | Styling and responsive layouts |
| JavaScript | Client-side interactions |
| Jinja2 | Primary HTML template rendering |
| Mako | Additional template-related technology detected in the repository |
| Flask-SQLAlchemy | ORM integration |
| SQLAlchemy | Database operations and data models |
| Flask-Migrate | Database migration management |
| Alembic | Database schema migration support |
| Flask-Login | User session and login management |
| Flask-WTF | Form handling and CSRF-related protection |
| Werkzeug | Password hashing and security utilities |
| Flask-Limiter | Request-rate limiting |
| Matplotlib | Charts and quality-analysis visualizations |
| openpyxl | Excel report generation |
| fpdf2 | PDF report generation |
| Pillow | Image processing |
| python-dotenv | Environment-variable configuration |
| pytest | Automated testing |

The exact functionality of each dependency depends on how it is used in the application.

### GitHub Language Composition

The repository's previously observed GitHub language breakdown was:

- Python: 46.8%
- HTML: 33.9%
- CSS: 11.2%
- JavaScript: 8.0%
- Mako: 0.1%

These percentages may change as the repository evolves.

---

## 🏗️ Application Architecture

QuizMaster follows a modular web application architecture.

```text
QuizMaster
    |
    ├── Frontend
    |     ├── HTML Templates
    |     ├── CSS Stylesheets
    |     └── JavaScript
    |
    ├── Flask Application
    |     ├── Authentication
    |     ├── Public Pages
    |     ├── Student Portal
    |     ├── Quiz Management
    |     ├── Administrator Portal
    |     └── TQM Workspace
    |
    ├── Backend Services
    |     ├── Grading and Quiz Attempts
    |     ├── Email and Token Handling
    |     ├── Reports and Exports
    |     ├── Charts and Quality Analysis
    |     ├── Upload Management
    |     └── Backup Operations
    |
    └── Database
          ├── User Records
          ├── Quiz and Question Records
          ├── Assessment Attempts and Results
          └── Quality and System Records
```

The application separates routes, models, services, templates, and static assets to support maintainability and organized development.

---

## 📁 Project Structure

The main project structure is organized as follows:

```text
QuizMaster/
├── app.py
├── wsgi.py
├── requirements.txt
├── .env.example
│
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── bootstrap.py
│   ├── cli.py
│   ├── security.py
│   ├── quality_goals.py
│   │
│   ├── blueprints/
│   │   ├── Public and authentication routes
│   │   ├── Student and account routes
│   │   ├── Quiz routes
│   │   ├── Administrator routes
│   │   └── Quality-management routes
│   │
│   ├── models/
│   │   └── Application data models
│   │
│   └── services/
│       └── Application and business logic
│
├── frontend/
│   ├── templates/
│   │   └── HTML templates
│   │
│   └── static/
│       ├── CSS
│       ├── JavaScript
│       └── Images and other assets
│
├── database/
│   └── migrations/
│
├── docs/
│   ├── screenshots/
│   └── DEVELOPMENT_DEFECTS.md
│
├── scripts/
├── tests/
│
└── tqm/
    └── output/
```

**Note:** The tree above summarizes the major directories. Individual route, model, service, and template filenames may differ from this abbreviated representation.

Runtime files, local databases, backups, uploads, and logs are stored under the configured instance or data directories. These should not be included in a public source repository.

---

## 💻 Requirements

Before running QuizMaster, ensure the following are available:

- Python 3.12 or a compatible supported Python version.
- Git.
- A modern web browser.
- A terminal such as PowerShell or Command Prompt.
- Internet access for installing dependencies.
- SMTP credentials if real email verification and password-reset delivery are required.
- A compatible relational database and driver if using a database other than the default SQLite configuration.

Check the installed versions:

```powershell
python --version
git --version
```

---

## ⚙️ Installation and Setup

The following instructions use Windows PowerShell.

### Step 1: Clone the Repository

```powershell
git clone https://github.com/Ashishdumka24/QuizMaster.git
cd QuizMaster
```

### Step 2: Create a Virtual Environment

```powershell
py -3.12 -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, use the appropriate execution-policy settings for your environment or activate the environment from Command Prompt:

```bat
.venv\Scripts\activate.bat
```

### Step 3: Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the project's dependencies:

```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and configure the required settings.

Never publish your local `.env` file or commit real credentials to GitHub.

### Step 5: Initialize and Run the Application

Start the application from the project root:

```powershell
python app.py
```

Open the local URL displayed in the terminal. The development server commonly uses:

http://127.0.0.1:5000

Keep the terminal open while using the application.

To stop the development server, press `Ctrl+C`.

**Important:** The Flask development server is intended for development and testing, not direct production deployment.

---

## 🔧 Environment Configuration

QuizMaster uses environment-based configuration. Consult `.env.example` and `backend/config.py` for the supported variable names and defaults.

Important configuration categories include:

| Setting | Purpose |
|---|---|
| `APP_ENV` | Application environment |
| `FLASK_DEBUG` | Development debugging configuration |
| `APP_TIMEZONE` | Application timezone |
| `APP_BASE_URL` | Base URL used when generating links |
| `SECRET_KEY` | Flask session and security secret |
| `TOKEN_PEPPER` | Additional secret for token-related security |
| `DATABASE_URL` | Database connection |
| `MAIL_SERVER` | SMTP server |
| `MAIL_PORT` | SMTP port |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password or provider-issued credential |
| `MAIL_DEFAULT_SENDER` | Default outgoing email address |
| `MAIL_DEV_OUTBOX` | Development email-outbox configuration |
| `INITIAL_ADMIN_EMAIL` | Optional initial administrator email |
| `INITIAL_ADMIN_PASSWORD` | Optional initial administrator password |
| `INITIAL_ADMIN_NAME` | Optional initial administrator name |
| `SESSION_COOKIE_SECURE` | Secure-cookie configuration for HTTPS |
| `RATELIMIT_STORAGE_URI` | Rate-limit storage configuration |
| `AUTO_BACKUP_ENABLED` | Automatic backup configuration |
| `BACKUP_KEEP` | Backup retention setting |

Use only the variable names actually supported by your configuration files.

### Generating a Secret Key

Generate a strong random secret using Python:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Use unique secrets for different environments. Never use publicly shared example secrets in production.

### Email Configuration

Real OTP verification and password-reset emails require working SMTP settings.

If the project is configured to use a development email outbox, that facility should only be used for local testing. It must not expose private verification messages or account-reset tokens in a public production environment.

---

## 🗄️ Database Management

QuizMaster uses SQLAlchemy-based database functionality with Flask-Migrate and Alembic migration support.

The default configuration uses SQLite, with the database location determined by the application configuration. The project can also be configured to use another supported relational database.

### Apply Database Migrations

```powershell
flask --app app db upgrade
```

### Create a Migration

After changing database models:

```powershell
flask --app app db migrate -m "Describe the schema change"
```

Apply the migration:

```powershell
flask --app app db upgrade
```

Review generated migration files before applying them to important data.

### Demo and Seed Data

The application provides seed-data functionality for supported baseline records and demonstration content.

Demo data is intended for development and evaluation. Review it before using the application with real users, and ensure demonstration accounts and sample records are not unintentionally exposed.

Back up important database records before performing migrations, restoring backups, or running commands that modify data.

---

## 🧭 Useful Commands

Run these commands from the project root with the virtual environment activated.

### View Available Flask Commands

```powershell
flask --app app --help
```

### Create an Administrator

```powershell
flask --app app create-admin
```

Follow the interactive prompts and use a unique, strong password.

### Seed Sample Data

```powershell
flask --app app seed
```

Review the command's help and implementation before using force or reset options.

### Create a Backup

```powershell
flask --app app backup
```

### Inspect Backup-Restore Options

```powershell
flask --app app restore-backup --help
```

Test backup restoration carefully, preferably using a separate copy of the database.

### Inspect Chart-Generation Options

```powershell
flask --app app generate-charts --help
```

### Inspect Data-Purge Options

```powershell
flask --app app purge --help
```

**Warning:** Backup restoration and data-purge operations can affect existing records. Verify their arguments and consequences before running them.

---

## 🧪 Testing

QuizMaster includes a pytest-based test suite covering application functionality and selected security and quality-related workflows.

Run the tests from the repository root:

```powershell
pytest
```

For detailed test output:

```powershell
pytest -v
```

Testing should cover the following areas:

- Registration and login.
- Authentication and authorization.
- Student and administrator access.
- Quiz creation and management.
- Question management.
- Quiz submission and grading.
- Score calculation and result history.
- Database operations and migrations.
- Form validation and error handling.
- TQM quality tools and reporting.
- Security controls and session behaviour.

The presence of tests does not guarantee that all application workflows are fully validated. Run the test suite and investigate failures before releasing a version.

---

## 📈 Total Quality Management (TQM)

Total Quality Management focuses on customer satisfaction, process improvement, quality measurement, defect prevention, and evidence-based decision-making.

QuizMaster incorporates a TQM workspace intended to demonstrate how these concepts can be applied to an online assessment platform.

### Quality Objectives

The project maintains quality-goal mapping in `backend/quality_goals.py`, including objectives identified as Q01–Q20.

The mapping should be used to connect course requirements to application functionality and evidence.

### Quality Tools

**1. Pareto Analysis**

Helps identify the most frequent or significant categories of recorded defects, supporting prioritization of corrective action.

**2. Fishbone Diagram**

Organizes potential causes of a problem into categories to support structured root-cause analysis.

**3. Failure Mode and Effects Analysis (FMEA)**

Records potential failure modes, their effects, causes, and risk-related information to help prioritize preventive action.

**4. Plan–Do–Check–Act (PDCA)**

Provides a continuous-improvement framework for planning a change, implementing it, evaluating results, and taking corrective action.

**5. SIPOC Analysis**

Maps suppliers, inputs, process steps, outputs, and customers to improve process understanding.

**6. Critical-to-Quality (CTQ)**

Helps translate user needs into measurable quality characteristics.

**7. Statistical Quality-Control Charts**

Provides visual methods for reviewing available process measurements and identifying patterns that may need investigation.

**8. Defect Logging and Reporting**

Maintains structured defect information and supports quality review, corrective action, and project documentation.

### Quality Goals in Practice

| Quality area | Application-related focus |
|---|---|
| Reliability | Validation, error handling, backups, and supported recovery workflows |
| Performance | Query efficiency, pagination, and reporting |
| Usability | Navigation, dashboards, themes, and user preferences |
| Security | Authentication, role checks, password hashing, and token handling |
| Data integrity | Validation, database constraints, and duplicate prevention |
| Maintainability | Modular routes, services, models, and configuration |
| Accessibility | Keyboard support, focus states, contrast, and motion preferences where implemented |
| Reporting | Assessment summaries and supported export formats |
| Continuous improvement | Defect analysis, FMEA, PDCA, and quality reporting |

The precise implementation status of each objective should be checked against the source code and the official course guidelines.

### TQM Project Documentation

Related project documentation includes:

- `backend/quality_goals.py`
- `docs/DEVELOPMENT_DEFECTS.md`
- `tqm/output/`

These files support review of quality objectives, documented defects, and generated analysis outputs.

QuizMaster's TQM features are intended for educational and project-evaluation purposes. Their results should be interpreted using the actual data and definitions in the application.

---

## 🔐 Security

Security is an important part of an online assessment platform because it handles user accounts, assessment records, and potentially private information.

QuizMaster contains security-oriented components, but secure production operation depends on correct configuration, implementation, and testing.

Recommended safeguards include:

- Secure password hashing.
- Server-side validation.
- Role-based authorization for protected routes and operations.
- Secure session configuration.
- HTTPS for production access.
- CSRF protection for applicable forms.
- Rate limiting for sensitive endpoints.
- Safe handling of verification and reset tokens.
- Restricted and validated file uploads.
- Protected database credentials.
- Regular dependency updates.
- Secure logging and error handling.
- Tested database backup and restoration procedures.
- Protection of administrator accounts and sensitive application settings.

### Protect Sensitive Files

Do not publish:

- `.env` files containing real secrets.
- Private database files.
- Backups containing user data.
- Logs containing sensitive information.
- Passwords, access tokens, or SMTP credentials.
- Private uploads or account information.
- Development-only email outboxes containing verification links or reset tokens.

Check Git tracking carefully. Adding a file to `.gitignore` does not remove it if it has already been committed.

If a real credential has been exposed, rotate it. Removing the file in a later commit does not make the old credential safe again.

---

## 🚀 Production Deployment

Before deploying QuizMaster publicly, configure a production environment rather than relying on the Flask development server.

The project provides a WSGI entry point through `wsgi.py`. Production server options include Waitress and Gunicorn, depending on the operating system and hosting environment.

### Production Checklist

- Configure a strong production secret key.
- Disable debug mode.
- Set the correct production environment and public base URL.
- Configure HTTPS and secure cookies.
- Set up reliable SMTP delivery.
- Apply database migrations.
- Use persistent database storage.
- Create and test backup procedures.
- Configure rate-limit storage appropriately for the deployment.
- Review administrator access and authorization.
- Remove development-only data and email-preview functionality from public access.
- Check error handling and application logs.
- Run automated tests.
- Verify mobile and desktop layouts.
- Test account recovery and quiz workflows.
- Monitor application availability and dependencies.

### Windows Deployment Example

After configuring the production environment and installing the required dependencies, a Waitress command may be used where supported:

```powershell
flask --app wsgi db upgrade
waitress-serve --listen=127.0.0.1:8000 wsgi:app
```

### Linux Deployment Example

With Gunicorn installed and correctly configured:

```bash
flask --app wsgi db upgrade
gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app
```

These are deployment examples, not a complete hosting configuration. A public deployment also requires appropriate network access, HTTPS termination, persistent storage, secrets management, and operational monitoring.

---

## 🛠️ Troubleshooting

### Missing Python Packages

Ensure the virtual environment is activated and install the project dependencies:

```powershell
pip install -r requirements.txt
```

### Database Migration Problems

Check the configured database URL and permissions, then inspect migration status and errors before applying changes.

```powershell
flask --app app db upgrade
```

Back up important data before making database changes.

### Email Verification Is Not Working

Check SMTP configuration, sender details, provider requirements, and application logs. Do not share credentials or verification tokens while troubleshooting.

### Login or Session Issues

Check browser cookie settings, session configuration, the application secret, and HTTPS settings. When deploying behind a reverse proxy, verify that proxy and trusted-header settings match the actual infrastructure.

### Port Already in Use

If port 5000 is occupied, configure an available port using the method supported by the application's entry point or hosting environment.

### Test Failures

Run:

```powershell
pytest -v
```

Review the first failing test, inspect the associated error, and confirm that dependencies and environment settings are correct.

---

## 🔮 Future Enhancements

Potential improvements for future releases include:

- Expanded quiz categories and difficulty levels.
- Additional assessment formats.
- Enhanced performance dashboards.
- More detailed quality reports.
- Improved accessibility.
- Broader automated test coverage.
- Continuous integration and deployment.
- Additional reporting and export options.
- Improved monitoring and operational diagnostics.
- Further scalability and database optimization.

These are potential enhancements and are not necessarily implemented in the current version.

---

## 🤝 Contributing

Contributions, suggestions, and bug reports are welcome.

To contribute:

1. Fork the repository.
2. Create a feature branch.
3. Implement your change.
4. Add or update tests where appropriate.
5. Run the test suite.
6. Submit a pull request explaining the changes.

Please do not include credentials, private user data, local database files, backups, or sensitive logs in commits or issue reports.

---

## 🎓 Academic Context

QuizMaster was developed in the context of the **BBAT104 Fundamental of TQM** course project.

It combines an online quiz and assessment workflow with quality-management concepts, defect analysis, reporting, and continuous-improvement tools.

The application is intended to demonstrate how digital systems can support structured evaluation and quality-focused decision-making.

The final academic submission should be checked against the official TQM guideline document to confirm that every required deliverable, dataset, report, and quality tool is included.

---

## 📄 License

No license is specified in this README.

If you intend to distribute QuizMaster as an open-source project, add an appropriate `LICENSE` file and ensure that the project's dependencies and included assets permit the intended use.

Until a license is added, others do not automatically receive permission to reuse, modify, or redistribute the project's code.

---

## 👨‍💻 Author

**Ashish Dumka**

GitHub: [@Ashishdumka24](https://github.com/Ashishdumka24)

Repository: [QuizMaster](https://github.com/Ashishdumka24/QuizMaster)

---



**QuizMaster**

*Learn Smarter · Assess Better · Improve Continuously* 🚀
