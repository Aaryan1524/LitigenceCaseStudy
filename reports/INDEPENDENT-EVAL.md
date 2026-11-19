# Independent Litigence tests and evals

This is an exported application snapshot, plus new tests and synthetic labels
written from `docs/contract.md` and `parallel-filings-brief.md`. The original
test/eval branches and datasets were not retrieved. The evaluator inspected the
implementation; this is not a claim of blind evaluation or a second-agent review.
Application files are unchanged. Their SHA-256 hashes and source revision are in
`reports/source-manifest.json`.

## Run

Use Python 3.10+ with SQLite 3.35+ (`UPDATE ... RETURNING` is required).

```sh
cd /Users/aaryan/Downloads/litigence-eval
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/run_checks.py
.venv/bin/python scripts/mutation_check.py
```

The existing temporary environment can also be used:

```sh
/tmp/litigence-eval-venv/bin/python scripts/run_checks.py
/tmp/litigence-eval-venv/bin/python scripts/mutation_check.py
```

Individual commands: `python -m pytest -q`, `python -m evals`.
The eval CLI supports `--data path.jsonl` and `--json-report path.json`.
The complete tested dependency versions are recorded in `reports/environment.txt`.
To recreate that environment, install with `pip install -r reports/environment.txt`.
Only fastapi, uvicorn, httpx and pytest are direct dependencies.

## What is exercised

| Area | Evidence |
| --- | --- |
| Intake | malformed JSON/fields; error precedence; missing, wrong, non-ASCII and other-tenant signatures; signed raw UTF-8 bytes; published example; original preserved on retry |
| Database | WAL, foreign keys, busy timeout, idempotent fixtures; tenant-local notice uniqueness; calendar uniqueness |
| Extraction and checking | first matching field; case/whole-word rules; injection text as data; missing/wrong fields; impossible dates; null dates; tenant-local matters; extractor faults versus database faults |
| Worker | text-only call; claim visible before extraction; drain once; skip nonreceived rows; persist pending/review results; stop on DB faults; actual CLI success/failure |
| Review/list | tenant-local lookups; early approval rejection; review flag clearing; idempotency; calendar/status rollback together; field shape, boolean flags and insertion order |
| Concurrency | two independent Python processes for duplicate intake, duplicate approval and workers; real file-backed SQLite; worker barrier forces both to participate; exact call accounting for 18 notices |
| Integrated path | signed intake → actual extractor/worker → approve → list, for both tenants sharing M-3108 |
| Eval runner | shared worker code path; data validation; each field at 90% passes, 85% fails; CLI nonzero on bad quality/data |

The 20 hand-labelled notices are balanced across tenants. They cover all four
filing types, shared and exclusive matters, unknown matters, impossible/leap
dates, null fields, first-match precedence, whole-word rules, case sensitivity,
and two instruction-injection examples. Labels are fixed, not computed by the
implementation. The runner calls `worker.checks.run_extraction` on an in-memory
database. It prints accuracy per field and exact-match accuracy, reports each
mismatch, and exits 1 if any field is below 0.90 (exit 2 for invalid data).

## How to read the results

`reports/tests.xml`, `reports/evals.json` and `reports/run.json` hold execution
evidence. `reports/mutations.json` holds test failures produced by deliberately
broken temporary copies. Mutation checks cover signature bypass, signing
reserialized JSON, cross-tenant lookup, reclaiming processing notices, missing
approval transactions, swallowed DB errors and acceptance of impossible dates.
They require a passing baseline and assertion failures, rather than import or
syntax errors. Neither the source snapshot nor the original repository is
mutated. These seven probes are not an exhaustive mutation score.

Passing this suite establishes the covered synthetic contract behavior. It does
not establish extraction quality on real legal notices, production security,
crash recovery, live network/proxy behavior, or throughput under sustained load.
The API is exercised in-process through ASGI, with independent processes used for
database concurrency. Crash recovery and route authentication are explicitly
outside this exercise. Instruction-like text containing an actual matching
`Matter ID:` label still follows the contract's first-match rule.
