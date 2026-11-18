# Task: worker (part B, shared check, evals runner)
Role `worker`. Branch `feat/worker`. Skill: `.claude/skills/worker-pipeline/`.
Owns: `worker/**`, `evals/__main__.py`. Reads: contract, brief, `app/` once merged in by the architect. Never touches: `evals/notices.jsonl`, `tests/`, `extractor/` internals (import `extract` only).
Tools the worker uses, and nothing else: `extract(text)` and `check(answer, tenant_id, conn)`.
Build: `worker/checks.py` (`check`, `run_extraction`, contract sections 4 and 5), `worker/run.py` (`run_once`, atomic claim per section 6), `worker/__main__.py` (`--once`), `evals/__main__.py` (section 10), which calls `run_extraction` and nothing else for checking.
Acceptance: with a fake extractor returning a bad answer, a notice ends `pending` with three nulls and `needs_review` true; `bash .claude/skills/worker-pipeline/scripts/two_workers.sh` reports each notice processed once; `python -m evals` runs against whatever `notices.jsonl` exists. Paste output.
