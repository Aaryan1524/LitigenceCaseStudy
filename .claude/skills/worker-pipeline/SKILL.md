---
name: worker-pipeline
description: Build and check the Litigence extraction worker. Use when writing worker/checks.py, worker/run.py, worker/__main__.py or the evals runner, or when verifying that two workers never process the same notice.
---

# Worker pipeline

The worker turns `received` notices into `pending` ones. It has exactly two tools:

| Tool | Sees | Never sees |
|---|---|---|
| `extract(text)` | the notice text | tenant, matters, secrets, `conn` |
| `check(answer, tenant_id, conn)` | the answer and that tenant's matters | other tenants' matters |

`run_extraction(text, tenant_id, conn, extractor=extract)` is `check(extractor(text), tenant_id, conn)` with exceptions turned into an invalid answer. The worker and `python -m evals` both call it. There is no second copy of the checks.

## Loop (`run_once`)
1. Claim one notice with the single UPDATE in `references/claim-and-status.md`. No row means done.
2. `result = run_extraction(row.text, row.tenant_id, conn, extractor)`.
3. Write the four fields and `status='pending'` where `status='processing'`.
4. Repeat. Print `processed <n>` as the last line.

## Rules
- Never SELECT then UPDATE to claim. The claim is one statement; the database decides who wins.
- `check` never raises for a bad answer: every bad shape maps to the invalid result. A `sqlite3.Error` from the matter lookup propagates; `run_once` leaves that notice `processing`, logs it and stops (contract section 6).
- Matter lookups are `(tenant_id, matter_id)`. M-3108 exists in both tenants.
- Pass `text` and nothing else into the extractor.

## Load when needed
- `references/claim-and-status.md`: claim SQL, status lifecycle, why rowcount matters.
- `references/validation-rules.md`: every invalid case and its result.
- `examples/good-answer.json`, `examples/bad-answers.json`: inputs for quick checks.
- `examples/worker-run.md`: one notice from `received` to `pending`.

## Scripts
- `bash .claude/skills/worker-pipeline/scripts/smoke.sh`: seed, insert one notice, run once, print the row.
- `bash .claude/skills/worker-pipeline/scripts/two_workers.sh [n]`: insert n notices, start two workers together, confirm the processed counts sum to n.
