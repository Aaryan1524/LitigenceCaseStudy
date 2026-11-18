# Runbook (architect)

## Phase 2 order
1. `scripts/agents.sh setup`: creates the clones and the venv (needs network for pip).
2. In three terminals: `scripts/agents.sh run api`, `run extract`, `run tests`.
3. At api's "db ready" checkpoint, run `scripts/agents.sh collect api`, then `git merge feat/api`, then `scripts/agents.sh sync worker`. In a fourth terminal: `scripts/agents.sh run worker`.
4. When the extract session has ended: `scripts/agents.sh run evals-data`. The script refuses earlier. Extract is frozen from then on.
5. Blind roles: `scripts/agents.sh check evals-data` and `check tests`; paste the output back to that agent.
6. Integrate on main in this order: api, extract, worker, evals-data, tests. Run `pytest -q` and `python -m evals`. Send only `scripts/agents.sh report tests` to the tests agent.
7. `scripts/agents.sh collect`, then commit `evidence/`.

## Requirement change mid-build
Commit to the `contract` branch (docs, tasks, plans, .claude, scripts only), then merge into main. Run `scripts/agents.sh amend <role>` for each affected agent, then message that agent.

## Phase 3
- Reviewer: `git switch main && scripts/agents.sh run reviewer`, read-only (plan mode).
- Demo of a protection: an agent changes intake to verify the signature over `json.dumps(parsed)` instead of the raw bytes. `pytest -k signature` then fails, because the signed example returns 403, not 200. Restore with `git checkout -- app/`. Run it once before relying on it.

## Outstanding (user)
Push to a private GitHub repo and add the collaborator: done by the user, not by agents.
