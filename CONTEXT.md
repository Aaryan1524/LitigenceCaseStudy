# Litigence parallel-filings: architect context

Paste or `@`-reference this file at the start of the Claude Code session. It is the full problem statement, restructured for architecting. Everything is synthetic.

## 0. How to use this in the CLI

Start in an empty git repo. First job of the session: produce Phase 1 artifacts only, no application code:

1. `CLAUDE.md` (shared rules for every agent)
2. `docs/contract.md` (DB schema, status values, function interfaces, HTTP behaviour table)
3. `tasks/<agent>.md`, one per agent, each with an acceptance check
4. At least one rule enforced by a hook, test or script, not prose
5. Commit, push to a private GitHub repo, add the collaborator we are given in chat

Suggested opening prompt:

> Read CONTEXT.md. You are the architect. Do not write application or test code. Propose the contract (schema, statuses, function signatures, HTTP behaviour table), the agent split with one task file and one acceptance check each, and one rule enforced mechanically. List open decisions before deciding them. Keep each file short.

## 1. Exercise constraints (process, not product)

- Agents write all application and test code, including temporary edits that prove a test catches a bug. The human hand-writes only instruction files, agent definitions, plans, prompts, hooks, config, shell commands.
- Python, SQLite, FastAPI or Flask. Direct deps allowed: fastapi or flask, uvicorn, httpx, pytest.
- Commit as you go. Push to a private GitHub repo at the end of each phase.
- Agents stay inside this repo. We must state the permission settings chosen and why.
- Give agents no data or credentials beyond this brief. Secrets below are test fixtures.
- Requirements will change partway through. Keep the contract easy to amend.

### Phases (43 minutes)

| Phase | Time | Deliverable |
|---|---|---|
| 1 Setup | 10 min, incl. 2-min walkthrough | Items in section 0, committed and pushed |
| 2 Build | 25 min | 2+ agents in parallel, each on its own branch or worktree, integrated on `main` |
| 3 Review | 8 min | Reviewer agent that did not write the code; decide on up to 2 findings; show one test failing when its protection is removed |

Phase 2 rules:
- Tests are written by a different agent from the code they test, working only from the brief and the contract.
- The agent that writes `extract` and the agent that writes `evals/notices.jsonl` never see each other's files. We must explain how we know each separation held.
- Narrate what each agent is doing and how it is checked.

Judging: setup quality and how agents are directed and checked, not completeness. Must have one integrated path and one safety test running by Phase 3. At the end we are asked what would break first in production.

## 2. Domain

Litigence hosts many law firms (tenants) on one service. A docket-monitoring vendor sends each firm court filing notices as text. An extraction step proposes the filing type, the matter, and the filed date. Staff approve before anything is docketed to a matter's calendar.

### Seed data

| Tenant | Inbox | Secret |
|---|---|---|
| alderbrook-law | dockets@alderbrook-law.example | alderbrook-fixture-key |
| fernwick-llp | dockets@fernwick-llp.example | fernwick-fixture-key |

| Matter | Tenant |
|---|---|
| M-3108 | alderbrook-law |
| M-3109 | alderbrook-law |
| M-3108 | fernwick-llp |
| M-4410 | fernwick-llp |

Matter IDs are unique within a tenant only. The two M-3108 are different matters. Every matter lookup must be keyed by (tenant, matter_id).

### Signed example (verified: this signature is correct for alderbrook-law)

Body is exactly this one line, no trailing newline:

```
{"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example","text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply."}
```
`X-Signature: 4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2`

Scheme: hex HMAC-SHA256 over the original raw body bytes, keyed with the tenant secret. Synthetic scheme, not a real vendor's.

## 3. System: four parts, one shared SQLite database

### Part A: intake, `POST /webhooks/notices`

Body is `application/json` with string fields `notice_id`, `inbox`, `text`. Header `X-Signature`.

Order of checks, all before any write:
1. Parse JSON; invalid JSON or missing field gives 400
2. Find tenant from `inbox`; unknown inbox gives 404
3. Verify signature over the original raw bytes (never re-serialized JSON); missing or wrong gives 403
4. Store with status `received`; return 200

Rules:
- Never calls the extractor.
- `notice_id` is stored once per tenant, even when two deliveries arrive at the same moment. A repeat returns 200 and keeps the original.

### Part B: extraction worker, `python -m worker --once`

Processes every `received` notice, then exits.

- Two workers started at the same moment never extract the same notice twice.
- The extractor receives the notice text only: never matter records, tenant names, or secrets. Tests can replace the extractor.
- The worker checks the extractor's answer in code:
  - Invalid answer (unknown `filing_type`; `filed_date` not a real calendar date; `matter_id` not a matter of that tenant; missing key or wrong type; extractor raised an error): store all three fields null, `needs_review = true`.
  - Valid answer with no matter: `needs_review = true`.
  - A null `filed_date` is valid.
  - In every case, status becomes `pending`.

### Part C: review API

`POST /tenants/{tenant}/notices/{notice_id}/approve`
- Dockets the notice to its matter's calendar and sets status `docketed`.
- Approving twice, even concurrently, creates exactly one calendar entry; both calls return 200.
- No matter (including a notice not yet extracted): 409.
- Unknown tenant, or notice not in that tenant: 404.

`GET /tenants/{tenant}/notices`
- Returns that tenant's notices only, as a JSON array with `notice_id`, `matter_id` (or null), `filing_type`, `filed_date`, `needs_review`, `status`.
- Known tenant with none: `[]`. Unknown tenant: 404.

### Part D: extractor and evals

- `extract(text)`: deterministic, local, no real model. Returns `filing_type` in {`complaint`, `motion`, `order`, `other`}, `matter_id` or null, `filed_date` (`YYYY-MM-DD`) or null.
- `evals/notices.jsonl`: 20 labelled synthetic notices, each with tenant, text, and the three expected fields after checking. Must include (a) a matter ID that exists only in the other tenant, (b) an impossible date, (c) a notice whose text tells the reader to ignore its instructions.
- `python -m evals`: runs each notice through the same extract-and-check code the worker uses, prints accuracy per field, exits non-zero if any field is below 0.90.

### Tests (written by a different agent from the code)

Must cover:
1. Bad signature
2. Duplicate `notice_id`
3. Two workers at once
4. Matter ID that exists only in the other tenant
5. The matter ID that exists in both tenants
6. A bad extractor answer
7. Approving twice

Plus one end-to-end test on integrated code: signed webhook, worker, approve, list.

Never weaken a test to hide a defect. If a test is wrong, say why before changing it.

## 4. Status model (as stated in the brief)

`received` (stored by intake) then `pending` (after worker, always) then `docketed` (after approve).

Notice fields after extraction: `matter_id`, `filing_type`, `filed_date` (all nullable), `needs_review`.

## 5. Where the brief is strict (design pressure points)

1. Signature is over raw bytes. Intake must read the body once and keep the bytes.
2. Dedupe and approve idempotency must hold under concurrency. Application-level check-then-insert is not enough; the database must enforce uniqueness (per tenant and notice for notices; per notice for calendar entries).
3. Worker claim must be atomic so two workers never process the same notice.
4. Tenant isolation: every matter lookup and every list query is tenant-scoped. A matter valid in tenant A must be rejected for a notice in tenant B.
5. The worker's check function and the evals runner must share one code path.
6. Extractor input is text only. This is a boundary worth enforcing mechanically.
7. A prompt-injection notice must not change behaviour: the extractor is deterministic and the worker validates output in code.

## 6. Open decisions for the architect to resolve in the contract

- Table layout and keys: tenants, matters (tenant_id, matter_id), notices (UNIQUE tenant + notice_id), calendar entries (UNIQUE per notice).
- How the worker claims a notice atomically, and whether a transient status is needed. If so, add it to the status list explicitly. Crash recovery is out of scope.
- Module layout and the exact signatures for `extract(text)` and the shared check function. Where the extractor is injected so tests can replace it.
- Precise HTTP behaviour table: check order and the response for every case, including approve on `received` vs `pending` with a null matter.
- What `needs_review` is for an approved notice, and whether approving a `needs_review` notice with a matter is allowed (the brief only blocks no-matter).
- Agent split and branch or worktree layout; which agent owns which files; what the guard hook denies.
- How each separation is proven (hook logs, worktree contents, tool-call logs).
- Permission settings for the agents and the reason for each.
- Which one rule is enforced mechanically (hook, test, or script).

## 7. Out of scope

OCR and PDFs, auth on GET and approve, recovering a crashed worker, a real vendor, a real model, a review UI, deployment, computing deadlines from a filing.

## 8. Final question to prepare for

"What do you think would break first in production?" Keep a running list during the build: concurrency under real load on SQLite, secret handling, the single-signature scheme, extractor quality on real notices, no worker recovery.
