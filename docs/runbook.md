# Runbook (architect)

## Build
1. `scripts/agents.sh setup`: creates one clone per role and the shared venv (needs network for pip).
2. Launch in parallel, each in the background:
   - `HEADLESS=1 scripts/agents.sh run extract`
   - `HEADLESS=1 scripts/agents.sh run api`
   - `HEADLESS=1 scripts/agents.sh run tests`
3. When extract has ended: `scripts/agents.sh evals-call`. It is one no-tools LLM call and refuses to start earlier. Extract is frozen from then on.
4. When api commits `CHECKPOINT: db ready`:
   1. `scripts/agents.sh collect api extract`
   2. `git merge feat/extract feat/api`
   3. `scripts/agents.sh sync worker`
   4. `HEADLESS=1 scripts/agents.sh run worker`
5. Follow-ups to a headless agent: `scripts/agents.sh resume <role> "<message>"`. For tests, send only `scripts/agents.sh report tests` output (ids and messages, no source), and only after checking its clone is clean.
6. Integrate on main: `scripts/agents.sh collect`, merge every `feat/<role>`, then run `pytest -q` and `python -m evals`.
7. `scripts/agents.sh audit`, then commit `evidence/`.

## Requirement change mid-build
1. Edit `docs/contract.md` on the `contract` branch. It carries docs, tasks, plans, `.claude` and scripts, never code.
2. Run `python3 scripts/packs.py` and commit.
3. Merge into main.
4. Run `scripts/agents.sh amend <role>` for each affected agent, then `resume` it.

This happened once for real: the seed fixtures. See the change log in `docs/contract.md`.

## Review
- `scripts/agents.sh setup reviewer`, then `HEADLESS=1 scripts/agents.sh run reviewer`. It is a fresh clone of main with an empty write allowlist.
- Fix at most two findings by resuming the owning agent. Findings in `extractor/` are documented won't-fix, because extract is frozen once the evals exist.
- The protection demo is an agent-made edit:
  1. api makes one commit labelled `DEMO:` that verifies the signature over `json.dumps(parsed)` instead of the raw bytes, then one commit that reverts it.
  2. The architect cherry-picks only the `DEMO:` commit onto a scratch branch from main, runs pytest, and saves the failing test ids to `evidence/`.
