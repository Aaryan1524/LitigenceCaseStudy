# Plan: reviewer
Context: CLAUDE.md, docs/contract.md, tasks/reviewer.md, integrated `main`. Read-only.

1. Run `pytest -q` and `python -m evals`; note results.
2. Walk the checklist in tasks/reviewer.md against the code, one item at a time, with file:line for each.
3. For each suspected defect, write the concrete scenario that breaks it.
4. Report at most 5 findings, most severe first. Do not fix anything.
