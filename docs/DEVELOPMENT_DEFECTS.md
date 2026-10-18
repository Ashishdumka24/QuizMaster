# Development defect log (real defects found while building QuizMaster)

These are genuine defects found while building QuizMaster (code review, automated tests and
strict template render checks). The same records are loaded into the in-app TQM defect log by
`flask --app app seed`, so the Pareto chart, fishbone and check sheet use real project data. Rows
DD-05 onwards were found by the pytest suite. No defect counts here are invented.

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
