# Development defect log (real defects found while building QuizMaster)

These are genuine defects found by the automated tests and render checks while the app was being
built. They are separate from the demo defect records seeded into the in-app TQM defect log, which
are clearly marked as illustrative examples.

| ID | Found by | Area | Description | Root cause | Fix | Fishbone category |
|----|----------|------|-------------|------------|-----|-------------------|
| DD-01 | pytest page render (`test_public_pages[/]`) | Templates | Every page crashed with `'current_user' is undefined` inside the brand macro | Jinja macros imported with `{% from %}` do not see the request context by default | Import macros `with context` in every template | Software Code |
| DD-02 | Manual render check before testing | Templates | Pagination macro could not compile (`invalid syntax for function call expression`) | Jinja allows only one `**kwargs` expansion per call; the macro used two | Merge the kwargs into one dict before `url_for` | Software Code |
| DD-03 | Strict-undefined render test | Templates | `caller()` guards in `empty` and `page_head` failed under strict undefined checking | The macros tested `caller` truthiness instead of `caller is defined` | Use `{% if caller is defined %}` | Software Code |
| DD-04 | Code review | Security | Marking notifications read redirected to `request.referrer` (could be an off-site URL) | Unvalidated redirect target | Always redirect to the internal notifications page | Software Code |
