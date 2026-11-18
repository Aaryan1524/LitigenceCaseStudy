# Task: reviewer (phase 3)
Role `reviewer`. Fresh session on integrated `main`. Read-only: write nothing but your report.
Check against `docs/contract.md`: raw-bytes signature, DB-enforced uniqueness, atomic claim, tenant scoping on every query, shared `run_extraction`, extractor receives text only, injection notice behaviour, approve ordering and idempotency.
Report at most 5 findings, most severe first, each with file and line, a concrete failing scenario, and a suggested fix. Do not fix anything.
Acceptance: each finding has a reproducible scenario, not a style opinion.
