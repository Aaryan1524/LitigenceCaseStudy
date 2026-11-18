# Plan: tests
Context: CLAUDE.md, docs/contract.md, parallel-filings-brief.md, tasks/tests.md. Write only `tests/**`. No application code exists in your checkout; write from the contract.

1. `tests/conftest.py`: fixtures for a temp db path (`tmp_path`), `LITIGENCE_DB` env, an app client built lazily (`create_app(db_path)` imported inside the fixture), a `sign(body_bytes, secret)` helper, and fake extractors (good, bad shapes, raising). Commit.
2. `tests/test_intake.py`: signed example 200 (exact bytes from section 8), bad and missing signature 403 with zero rows, 400 and 404 cases, duplicate sequential and concurrent (threads with separate clients) leaves one row. Commit.
3. `tests/test_worker.py`: `check` table cases, cross-tenant matter, M-3108 per tenant, bad extractor shapes and raising, two concurrent `run_once` (threads or subprocesses) process each notice once. Commit.
4. `tests/test_review.py`: approve 409 on received and null matter, 404 cases, approve twice sequential and concurrent gives one calendar row and two 200s, list scoped per tenant, `[]` and 404. Commit.
5. `tests/test_boundaries.py`: `extract` signature is exactly (text); AST scan of `app/**/*.py` finds no import of `extractor` or `worker` (skip if `app/` missing). Commit.
6. `tests/test_e2e.py`: signed webhook -> `run_once` -> approve -> list shows `docketed`. Commit.
7. List every test function you wrote, grouped by file, with the brief requirement each covers.
CHECKPOINT: report done. The architect runs `pytest --collect-only -q` on your branch and sends the output; fix collection errors only. Later the architect sends pytest output from main; diagnose without weakening tests.
