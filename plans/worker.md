# Plan: worker
Context: CLAUDE.md, docs/contract.md, tasks/worker.md, skill `.claude/skills/worker-pipeline/`. Write only `worker/**`, `evals/__init__.py`, `evals/__main__.py`.
`app/db.py` is already merged into your checkout. Import `extract` from `extractor`; if `extractor/` is not there yet, keep the default import lazy so your own checks run with fake extractors.

1. Read SKILL.md and both references.
2. `worker/__init__.py`, `worker/checks.py`: `check` per references/validation-rules.md, `run_extraction` per contract section 4. Verify every entry in examples/bad-answers.json gives the invalid result and good-answer.json gives its expected result (one `python -c` loop). Commit.
CHECKPOINT: report the check results.
3. `worker/run.py`: `run_once` with the claim and finish SQL from references/claim-and-status.md; one connection per run; commit per notice. `worker/__main__.py`: `--once` flag, prints `processed <n>`. Commit.
4. Verify: `bash .claude/skills/worker-pipeline/scripts/smoke.sh` (needs `extractor/`; if absent, run_once with a fake extractor in `python -c`), then `scripts/two_workers.sh 200` must print PASS. Commit.
CHECKPOINT: report the two_workers output.
5. `evals/__init__.py`, `evals/__main__.py` per contract section 10, calling `run_extraction` only. Missing `notices.jsonl` -> clear error, exit 2. Commit.
6. Acceptance from tasks/worker.md. Paste output.
