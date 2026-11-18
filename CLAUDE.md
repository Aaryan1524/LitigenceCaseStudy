# Litigence parallel filings: rules for every agent

Before anything, read `docs/contract.md`, `tasks/<your role>.md` and `plans/<your role>.md`. The contract is the only source of truth for schema, statuses, signatures and HTTP behaviour. The brief is `parallel-filings-brief.md`. Your role is in `.claude/role`.

## Rules
1. Stay inside your own checkout. Touch only the files your task file says you own.
2. Do not edit `docs/contract.md`, `CLAUDE.md` or anything under `.claude/`. If the contract is wrong or unclear, stop and report it. The architect amends it.
3. Follow your plan file step by step. Commit after each step. Stop at each `CHECKPOINT` line and report.
4. Never weaken a test to make it pass. If a test looks wrong, say why before changing it.
5. Python 3, SQLite, FastAPI. Direct dependencies: fastapi, uvicorn, httpx, pytest. Nothing else.
6. All data is synthetic. Use only the fixtures in the contract. Never invent credentials.
7. Uniqueness and atomicity are enforced by the database (UNIQUE constraints, single-statement UPDATEs), never by check-then-insert in Python.
8. Every matter lookup and every list query is keyed by `(tenant_id, matter_id)`.
9. Do not push, fetch, merge or switch branches. The architect integrates on `main`.
10. Commit with one plain line: `git commit -m "message"`. No `$(...)`, heredocs, backticks or shell variables; the guard refuses them.
11. Finish by running your task's acceptance check and pasting its output. Roles without code execution (evals-data, tests) report what they wrote; the architect runs their check and sends back the output.

## Mechanically enforced (do not try to route around it)
- Separate checkouts: each agent works in its own clone with only its own files on disk.
- Path guard: `.claude/hooks/path_guard.py` runs before every tool call. It reads your role from `.claude/role`, allows only the paths and commands listed for that role in `.claude/roles.json`, and logs every call to `.claude/guard.log`.
- Import boundary: a test fails if anything under `app/` imports `extractor` or `worker`.
- Extractor boundary: a test fails if `extract` takes anything but one parameter, `text`.

## Layout
`app/` intake, review API, db. `worker/` worker and shared check. `extractor/` extract. `evals/` data and runner. `tests/` tests. `docs/` contract. `tasks/` and `plans/` one file per role. `.claude/skills/worker-pipeline/` worker skill.
