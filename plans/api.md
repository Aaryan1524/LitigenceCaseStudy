# Plan: api
Context: CLAUDE.md, docs/contract.md, tasks/api.md. Write only `app/**`.

1. `app/__init__.py`, `app/constants.py` (STATUSES, FILING_TYPES from contract section 1). Commit.
2. `app/db.py`: `connect`, `init_db`, `matter_ids` exactly per sections 2 and 4. Pragmas: foreign_keys, WAL, busy_timeout 5000. Seed with INSERT OR IGNORE. Verify: `python -c "from app.db import connect,init_db,matter_ids; c=connect(':memory:'); init_db(c); init_db(c); print(matter_ids(c,'alderbrook-law'))"` prints the two matters. Commit.
CHECKPOINT: report "db ready" with that output. The architect merges this commit to main so the worker can start. Continue without waiting.
3. `app/main.py`: `create_app(db_path)`. Intake route: read `await request.body()` once; parse; validate fields (400); find tenant by inbox (404); HMAC over the same bytes with `hmac.compare_digest` (403); INSERT ... ON CONFLICT DO NOTHING; 200. Commit.
4. Approve route per section 7 table, in one transaction (`BEGIN IMMEDIATE`). Commit.
5. List route per section 7. Commit.
6. Acceptance from tasks/api.md with TestClient, using the exact bytes from section 8 (send with `content=`, not `json=`). Paste output.
CHECKPOINT: report done.
