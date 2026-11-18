# Task: tests (all tests and the end-to-end test)
Role `tests`. Branch `feat/tests`.
Owns: `tests/**`. Reads: `docs/contract.md` and `parallel-filings-brief.md` only.
Hard separation: your checkout has no application code and never will. Write tests against the interfaces in contract section 4 and the HTTP behaviour in section 7. Import application modules inside fixtures or test bodies, never at module level, so collection works before the code exists.
Build, using a temp db per test:
1. Bad signature: 403 and no row written.
2. Duplicate notice_id, including two simultaneous deliveries: one row.
3. Two workers at once: each notice processed once.
4. Matter valid only in the other tenant: three nulls and needs_review.
5. M-3108 resolves per tenant.
6. Bad extractor answer: several shapes, and an extractor that raises.
7. Approving twice, including concurrently: one calendar row and two 200s.
8. Boundaries: `extract` takes exactly one parameter; nothing under `app/` imports `extractor` or `worker` (parse with `ast`, skip if `app/` is absent).
9. End to end: signed webhook, `run_once`, approve, list.
Acceptance: `pytest --collect-only -q` collects every test without errors. When the architect sends you `pytest` output from `main`, report each failure with its probable cause; do not edit a test to turn it green without saying why the test was wrong.
