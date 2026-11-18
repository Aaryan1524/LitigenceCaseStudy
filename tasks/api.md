# Task: api (parts A and C, database)
Role `api`. Branch `feat/api`.
Owns: `app/**`. Reads: contract, brief. Never touches: `worker/`, `extractor/`, `evals/`, `tests/`.
Build: `app/__init__.py`, `app/constants.py`, `app/db.py` (schema, seed, pragmas, `matter_ids`), `app/main.py` (`create_app`), intake and review routes exactly per contract section 7. Nothing in `app/` imports `extractor` or `worker`.
Acceptance: using `fastapi.testclient.TestClient` on a temp db, POST the signed example from contract section 8 and get 200; the same body with one byte changed gets 403; posting it twice leaves one row; `GET /tenants/alderbrook-law/notices` lists it with status `received`. Paste the script and its output.
