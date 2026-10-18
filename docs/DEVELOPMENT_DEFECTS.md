# Development defect log (real defects found while building QuizMaster)

These are genuine defects found while building QuizMaster (code review, automated tests and
strict template render checks). The same records are loaded into the in-app TQM defect log by
`flask --app app seed`, so the Pareto chart, fishbone and check sheet use real project data. Rows
DD-05 onwards were found in the second build phase (tests, process review and visual checks). No defect counts here are invented.

| ID | Found by | Area | Description | Root cause | Fix | Fishbone category |
|----|----------|------|-------------|------------|-----|-------------------|
| DD-00a | Code review | Calendar | Leftover placeholder code in calendar view | Unfinished experimental code | Removed; uses `to_local()` | Software Code |
| DD-00b | Code review | Preferences | Preference checkboxes could not be switched off | Absent checkboxes never treated as False | `_full_form` flag | Software Code |
| DD-00c | Preview testing | Security headers | App preview blocked inside embedding iframe | frame-ancestors always SAMEORIGIN | `FRAME_ANCESTORS` setting | Infrastructure |
| DD-00d | Preview testing | Sessions | Session cookie not sent when embedded cross-site | SameSite=Lax withheld in iframes | `SESSION_COOKIE_SAMESITE` setting | Infrastructure |
| DD-00e | Code review | Admin filters | Fragile UTC conversion in date-range filter | Ad-hoc tz construction | `datetime.timezone.utc` | Software Code |
| DD-01 | pytest page render (`test_public_pages[/]`) | Templates | Every page crashed with `'current_user' is undefined` inside the brand macro | Jinja macros imported with `{% from %}` do not see the request context by default | Import macros `with context` in every template | Software Code |
| DD-02 | Manual render check before testing | Templates | Pagination macro could not compile (`invalid syntax for function call expression`) | Jinja allows only one `**kwargs` expansion per call; the macro used two | Merge the kwargs into one dict before `url_for` | Software Code |
| DD-03 | Strict-undefined render test | Templates | `caller()` guards in `empty` and `page_head` failed under strict undefined checking | The macros tested `caller` truthiness instead of `caller is defined` | Use `{% if caller is defined %}` | Software Code |
| DD-04 | Code review | Security | Marking notifications read redirected to `request.referrer` (could be an off-site URL) | Unvalidated redirect target | Always redirect to the internal notifications page | Software Code |
| DD-05 | Strict-undefined render test (`/admin/quizzes/new`) | Admin | New-quiz form crashed in strict mode | View did not pass `problems` | Pass `problems=[]` | Software Code |
| DD-06 | Process review | Workflow | A bug fix (DD-05) was committed before the test suite was re-run | No rule required a green run before committing | Suite re-run in normal and strict mode; pre-commit checklist added to README | Process |
| DD-07 | Review against the guideline PDF | TQM docs | Q01–Q20 feature mapping did not use the guideline's exact wording | Mapping first written from memory | Transcribed verbatim into `backend/quality_goals.py` | People |
| DD-08 | New auth tests | Test suite | Logged-in user leaked between independent test clients | Fixture held one app context open, so Flask-Login's cached user in `g` was shared | Requests run outside a long-lived app context | Software Code |
| DD-09 | New auth tests | Forgot password | Dev-outbox notice appeared only for existing accounts (enumeration in dev mode) | Notice tied to an email actually being written | Notice shown for every request in outbox mode | Software Code |
| DD-10 | Icon instrumentation in tests | UI | 8 icon names used by templates were undefined (silent fallback glyph) | No check between templates and `icons.py` | Icons added; test fails on any missing icon | Software Code |
| DD-11 | Visual check of generated PNGs | SQC charts | Pareto labels wrapped mid-word; fishbone cause labels overlapped a neighbouring bone | Character-based wrapping; bones too close | Word-safe wrapping; fishbone re-spaced with two-line labels | Software Code |
