# Frontend — what users see

Everything the browser receives. It contains no Python business logic. Flask renders these
templates on the server, so pages still work with JavaScript turned off.

```
frontend/
├── templates/               Jinja2 HTML templates
│   ├── layouts/             base, public, auth and app (sidebar) shells
│   ├── macros/ui.html       reusable UI pieces (fields, badges, charts, pagination…)
│   ├── public/              home, explore, features, about, help, legal pages
│   ├── auth/                login, register, OTP verify, forgot / reset password
│   ├── student/             dashboard, history, results, notifications, feedback
│   ├── quiz/                quiz detail, player, result, certificate, leaderboard, calendar
│   ├── account/             profile, settings, security
│   ├── admin/               admin console (users, quizzes, question bank, analytics…)
│   ├── tqm/                 TQM centre: defects, Pareto, fishbone, FMEA, PDCA, SIPOC/CTQ, report
│   ├── emails/              HTML email templates (OTP, reset, notices)
│   └── errors/              friendly 400/403/404/429/500 pages
└── static/
    ├── css/                 core (design tokens) · layout · components · pages
    ├── js/                  core.js (UI behaviours) · charts.js (SVG charts) · player.js · theme-init.js
    └── img/                 favicon / brand assets
```

The Content-Security-Policy is `script-src 'self'`, so no inline scripts are allowed. Every
behaviour is attached from `static/js` through `data-*` attributes.
