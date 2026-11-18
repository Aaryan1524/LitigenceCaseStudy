# Litigence live exercise: direct several coding agents at once (43 minutes)

## How this works

- Agents write all application and test code, including any temporary edits to prove a test catches a bug. You
  may hand-write instruction files (CLAUDE.md, AGENTS.md), agent definitions, plans, prompts, hooks, configuration and
  shell commands. Reading code and directing targeted fixes is expected.
- Use Claude Code, Codex, or both. Start from an empty git repository. Python, SQLite, and FastAPI or Flask. Allowed
  direct dependencies: fastapi or flask, uvicorn, httpx and pytest; their own dependencies are fine. Commit as you
  go, and push to a private GitHub repository at the end of each phase. Add the GitHub user we give you in the chat
  as a collaborator and paste the link in the chat.
- Keep agents limited to this repository, and tell us what permission settings you chose and why.
- **Phase 1, setup (10 minutes, including a 2-minute walkthrough to us).** Before any application code exists, commit:
  your instruction files; a shared contract every agent works from (database schema, status values, function
  interfaces); one task per agent, each with an acceptance check; and at least one rule enforced by a hook, test or
  script rather than by prose.
- **Phase 2, build (25 minutes).** Run at least two coding agents at the same time on different parts (separate
  sessions or subagents), each on its own branch or git worktree, then integrate their work on `main`. Divide the
  four parts below however you think best, with two separations: tests are written by a different agent from the code
  they test, working from this brief and your contract; and the agent that writes `extract` and the agent that writes
  `evals/notices.jsonl` never see each other's files. Tell us how you know each separation held. Talk us through
  what each agent is doing and how you check it.
- **Phase 3, review (8 minutes).** Have the integrated work reviewed by an agent that did not write it, and decide
  what to do with up to two findings. Also show us one test failing when the protection it covers is removed.
- We are judging your setup and how you direct and check the agents, not how much gets finished. An unfinished system
  is fine, but have one integrated path and one safety test running for Phase 3. Requirements will change partway
  through, as they do with customers.
- Everything below is synthetic. Do not give your agents any other data or credentials.

## Context

Litigence runs many law firms (tenants) on one service. A docket-monitoring vendor sends each firm the court filing
notices on its matters, already converted to text. An extraction step proposes what each filing is and which matter
it belongs to; staff approve before anything is docketed to a matter's calendar.

Seed data (all synthetic; the secrets are test fixtures):

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

Matter IDs are unique within a tenant only: alderbrook-law's M-3108 and fernwick-llp's M-3108 are different matters.

Signed example (correct signature for alderbrook-law; the body is exactly this one line):

```
body:        {"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example","text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply."}
X-Signature: 4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2
```

## The system: four parts sharing one SQLite database

**Part A, intake.** `POST /webhooks/notices`, body `application/json` with string fields `notice_id`, `inbox` and
`text`. Header `X-Signature` = hex HMAC-SHA256 of the original raw body bytes, keyed with the tenant's secret. This is
a synthetic scheme for the exercise, not a real vendor's.

1. Parse the body to find the tenant from `inbox`, then check the signature over the original bytes before any write.
   Invalid JSON or a missing field returns 400; an unknown `inbox` returns 404; a missing or wrong signature returns
   403. Accepted notices return 200 and are stored with status `received`. This route never calls the extractor.
2. The vendor retries deliveries, sometimes two at the same moment. A `notice_id` is stored once per tenant, even
   when two deliveries arrive together. A repeat returns 200 and keeps the original.

**Part B, extraction worker.** `python -m worker --once` processes every `received` notice, then exits.

3. Two workers started at the same moment never extract the same notice twice.
4. Pass the extractor the notice text only, never matter records, tenant names or secrets. Tests can replace it.
5. Check its answer in code. An unknown `filing_type`, a `filed_date` that is not a real calendar date, a
   `matter_id` that is not a matter of that tenant, a missing key or wrong type, or an extractor error: store all
   three fields null with `needs_review` true. A valid answer with no matter also gets `needs_review` true. In every
   case the notice's status becomes `pending`. A null `filed_date` is valid.

**Part C, review API.**

6. `POST /tenants/{tenant}/notices/{notice_id}/approve` dockets the notice to its matter's calendar and sets its
   status to `docketed`. Approving twice, even twice at the same moment, creates exactly one calendar entry and
   returns 200 both times. A notice with no matter, including one not yet extracted, returns 409. An unknown tenant,
   or a notice that is not in that tenant, returns 404.
7. `GET /tenants/{tenant}/notices` returns that tenant's notices only, as a JSON array with `notice_id`, `matter_id`
   (or null), `filing_type`, `filed_date`, `needs_review` and `status`. A known tenant with no notices returns `[]`;
   an unknown tenant returns 404.

**Part D, extractor and evals.**

8. No real model: a deterministic local `extract(text)` returning `filing_type` (one of `complaint`, `motion`,
   `order`, `other`), `matter_id` (or null) and `filed_date` (`YYYY-MM-DD` or null).
9. `evals/notices.jsonl` holds 20 labelled synthetic notices, each with its tenant, its text and the three expected
   fields after checking. Include a matter ID that exists only in the other tenant, an impossible date, and a notice
   whose text tells the reader to ignore its instructions.
10. `python -m evals` runs each notice through the same extract-and-check code the worker uses, prints accuracy per
    field, and exits non-zero if any field is below 0.90.

**Tests.**

11. Cover a bad signature, a duplicate `notice_id`, two workers at once, a matter ID that exists only in the other
    tenant, the matter ID that exists in both tenants, a bad extractor answer, and approving twice. One end-to-end
    test runs the whole path on the integrated code: signed webhook, worker, approve, list. Do not weaken a test to
    hide a defect; if a test is wrong, say why before changing it.

Out of scope: OCR and PDFs, authentication on the GET and approve routes, recovering a worker that crashed part-way, a
real vendor, a real model, a review UI, deployment, computing deadlines from a filing.

At the end we will ask what you think would break first in production.
