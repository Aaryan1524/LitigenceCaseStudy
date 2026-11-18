# Litigence parallel filings: rules for every agent

Before anything, read `context/<your role>.md`. It holds your task, your plan and exactly the contract sections you need; it is generated from `docs/contract.md`, the only source of truth. Your role is in `.claude/role`.

## Rules
1. Stay inside your own checkout. Touch only the files your task file says you own.
2. Do not edit `docs/contract.md`, `CLAUDE.md` or anything under `.claude/`. If the contract is wrong or unclear, stop and report it. The architect amends it.
3. Follow your plan step by step without asking questions. Commit after each step. At a `CHECKPOINT` line, commit with a message starting `CHECKPOINT: ` and keep going.
4. Never weaken a test to make it pass. If a test looks wrong, say why before changing it.
5. Python 3, SQLite, FastAPI. Direct dependencies: fastapi, uvicorn, httpx, pytest. Nothing else.
6. All data is synthetic. Use only the fixtures in the contract. Never invent credentials.
7. Uniqueness and atomicity are enforced by the database (UNIQUE constraints, single-statement UPDATEs), never by check-then-insert in Python.
8. Every matter lookup and every list query is keyed by `(tenant_id, matter_id)`.
9. Do not push, fetch, merge or switch branches. The architect integrates on `main`.
10. Commit with one plain line: `git commit -m "message"`. No `$(...)`, heredocs, backticks or shell variables; the guard refuses them.
11. Finish by running your task's acceptance check and pasting its output. You cannot stop with uncommitted work or with files outside your slice: a Stop gate checks both.

## Mechanically enforced (do not try to route around it)
- Separate checkouts: each agent works in its own clone with only its own files on disk.
- Commit stamps: a git hook adds `Agent-Role` and `Agent-Session` trailers to every commit.
- Stop gate: `.claude/hooks/gate.py` refuses to let you finish with uncommitted work, files outside your slice, or modules that fail to import.
- Path guard: `.claude/hooks/path_guard.py` runs before every tool call. It reads your role from `.claude/role`, allows only the paths and commands listed for that role in `.claude/roles.json`, and logs every call to `.claude/guard.log`.
- Import boundary: a test fails if anything under `app/` imports `extractor` or `worker`.
- Extractor boundary: a test fails if `extract` takes anything but one parameter, `text`.

## Layout
`app/` intake, review API, db. `worker/` worker and shared check. `extractor/` extract. `evals/` data and runner. `tests/` tests. `docs/` contract. `context/` one generated pack per role. `.claude/agents/` one definition per role. `.claude/skills/worker-pipeline/` worker skill.
