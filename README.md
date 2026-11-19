# Litigence Parallel Filings

My submission for the Litigence exercise in
[parallel-filings-brief.md](parallel-filings-brief.md): direct several coding
agents at once to build a multi-tenant docket service. The brief judges the
setup and how the agents are directed and checked, so this README follows
the brief's own phases. Every row links to the evidence.

## Scorecard against the brief

| The brief asks for | Status | Where |
|---|---|---|
| Instruction files | Done | [CLAUDE.md](CLAUDE.md), [.claude/agents/](.claude/agents/) |
| A shared contract (schema, statuses, interfaces) | Done | [docs/contract.md](docs/contract.md) |
| One task per agent, each with an acceptance check | Done | [tasks/](tasks/), [plans/](plans/) |
| At least one rule enforced by a hook, test or script | Done: 2 hooks, 1 test, 1 script | [Phase 1](#phase-1-setup) |
| Permission settings and why | Done | [docs/permissions.md](docs/permissions.md) |
| 2+ agents at the same time, each on its own branch, integrated on `main` | 3 at once, 5 in all, each on a `feat/<role>` branch | [Phase 2](#phase-2-build) |
| Tests written by a different agent, from the brief and contract | Done, and shown | [Separation 1](#separation-1-tests-vs-code) |
| `extract` and `evals/notices.jsonl` authors never see each other's files | Done, and shown | [Separation 2](#separation-2-extract-vs-eval-data) |
| Handle a requirement change partway through | 3 contract amendments, pushed to agents | [Changes](#requirement-changes) |
| Review by an agent that did not write the code; decide on up to 2 findings | 5 findings: 2 fixed, 3 deferred | [Phase 3](#phase-3-review) |
| One test failing when its protection is removed | Done: 7 failures | [Phase 3](#phase-3-review) |
| One integrated path and one safety test running | Both suites pass on `main` | [Run it](#run-it) |
| What breaks first in production | Answered | [Production](#what-breaks-first-in-production) |

## Phase 1: setup

**Instruction files.**
- [CLAUDE.md](CLAUDE.md) holds the rules every agent loads.
- Each role is defined in [.claude/agents/](.claude/agents/), with its own
  model, tools and a short prompt.

**Contract.** [docs/contract.md](docs/contract.md) is the single source of
truth:
- tables and keys, including uniqueness constraints enforced by the
  database;
- status values, including a `processing` claim status that I added;
- exact function signatures, including where the extractor is injected;
- an HTTP table giving the response for every case, in check order.

**Tasks.** Each agent has a task file in [tasks/](tasks/), with an
acceptance check, and a step-by-step plan in [plans/](plans/).
[scripts/packs.py](scripts/packs.py) merges the task, the plan and only the
contract sections that role needs into one file per agent, in
[context/](context/). Each file is 600 to 1,000 words.

**Rules enforced mechanically, not by prose:**
- [.claude/hooks/path_guard.py](.claude/hooks/path_guard.py) runs before
  every tool call. It allows only the files and commands in the role's
  allowlist, and logs every call to a hash-chained log.
- [.claude/hooks/gate.py](.claude/hooks/gate.py) is a Stop hook. An agent
  cannot finish with uncommitted work, files outside its slice, or modules
  that fail to import.
- A test fails if anything under `app/` imports the extractor or worker,
  because intake must never call the extractor.
- [scripts/agents.sh](scripts/agents.sh) enforces run order: the extract
  agent refuses to start if eval data exists anywhere on disk.

I tested the guard in real agent sessions before the build: 17 probes,
each blocked or allowed as designed
([evidence/phase1-guard-test.md](evidence/phase1-guard-test.md)).

**Permissions.** Each agent:
- works only in its own clone;
- has no network tools, no MCP connectors, no subagents and no pip;
- cannot touch the contract, the hooks or `.git`;
- runs headless, so anything not explicitly allowed is denied.

Every setting and its reason is in [docs/permissions.md](docs/permissions.md).

## Phase 2: build

| Agent | Built | Model | How I checked it |
|---|---|---|---|
| api | intake, approve, list, database | Opus | its acceptance check, Stop gate, then the tests |
| worker | claim loop, `check()`, evals runner | Opus | two-worker race script (200 notices, counts sum exactly), Stop gate, tests |
| extract | `extract(text)` | Haiku | acceptance check on the brief's example, Stop gate |
| tests | the test suite | Opus | collection check run by me; it cannot run code |
| evals-data | 20 labelled notices | one LLM call, no tools | format check by script |

- **Parallelism and branches.** extract, api and tests ran at the same time.
  The worker started automatically when api committed
  `CHECKPOINT: db ready`. Each agent worked on its own `feat/<role>`
  branch, in its own git clone, and I merged them on `main`. Start and end
  times are in [evidence/sessions.log](evidence/sessions.log).
- **Result of the first integration:** 143 tests passed, evals 1.00.
- **Cost of the whole build and review:** $6.02 in agent sessions.

### Separation 1: tests vs code

- **How it was enforced:**
  - The tests agent's clone never contained `app/`, `worker/` or
    `extractor/`.
  - It had no `python` or `pytest`, so it could not run code.
  - I ran its tests and sent back only test names and one-line messages.
- **How I know it held:**
  - Its guard log shows every file it read.
  - The audit checks that it read nothing it hadn't written.
  - Every commit is stamped with its role and session.

One gap: a later merge of mine put three code files into its git history.
They were never on disk, and the agent made no call that could read them.
The audit still flags it ([incident 4](evidence/incidents.md)).

### Separation 2: extract vs eval data

- **How it was enforced:**
  - The eval data was written by a single LLM call with no tools at all,
    from an empty folder. It took 1 turn, with no tool calls.
  - The script made extract finish before the eval data existed anywhere
    on disk, and froze extract afterwards.
- **How I know it held:**
  - [evidence/audit.md](evidence/audit.md) checks git's content hashes: the
    eval file never entered extract's git store, and the extractor never
    entered the eval-data clone's.
  - The session log shows the order.
  - Every audit check has a negative test showing it can fail.

You can rerun the extract check yourself from the clone bundle in
[evidence/clones/](evidence/clones/).

### Requirement changes

Changes went through a `contract` branch that never carries code. I
regenerated the context files, merged the branch into the affected agents'
clones, and resumed them. This happened three times:

1. **Seed data.** The api agent found the seed data missing from its
   context file. It stopped instead of inventing it, and I added the
   fixtures to the contract.
2. **Database errors.** After review, the contract changed so a database
   error is never stored as an invalid answer.
3. **Signature header.** Also after review, a non-ASCII signature header is
   now a 403.

Each change is in the change log at the end of
[docs/contract.md](docs/contract.md).

## Phase 3: review

A fresh reviewer agent read `main` from its own read-only clone. It found 5
issues; I acted on two
([evidence/phase3-review.md](evidence/phase3-review.md)):

| Finding | Decision |
|---|---|
| A database error during matter lookup was saved as an invalid answer, silently losing a correct extraction | **Fixed** by the worker agent, with new tests from the tests agent |
| A non-ASCII signature header returned 500, not 403 | **Fixed** by the api agent |
| Malformed but signed bodies return 500 (2 findings) | Deferred: real, but it needs a malformed vendor payload |
| Blocking SQLite inside an async handler | Deferred: a latency issue, listed under production |

**Protection removed, test fails.** I had the api agent compute the
signature over re-serialized JSON instead of the raw bytes. 7 tests failed,
including the brief's own signed example. The agent's revert restored a full
pass ([evidence/phase3-demo.md](evidence/phase3-demo.md)).

## Independent second suite

After the build, I moved the pipeline's tests off `main`. I had Codex write
a second suite and eval set from an export of the code and the contract,
with no access to the first suite or its labels. That suite is what's on
`main` now.

| | Pipeline suite (`feat/tests`) | Codex suite (`main`) |
|---|---|---|
| Tests | 156 passed | 160 passed |
| Evals | 1.00 per field | 100% per field |
| Catches the other's 7 deliberate defects | 7 / 7 | 7 / 7 |

## Run it

```bash
pip install -r requirements.txt
python scripts/run_checks.py      # tests (incl. end-to-end: signed webhook → worker → approve → list), evals, hashes
python scripts/mutation_check.py  # 7 deliberate defects, each must make a test fail
python scripts/cross_check.py     # the pipeline suite on the same code and the same 7 defects
```

The orchestration commands are in [docs/runbook.md](docs/runbook.md). It
starts with `scripts/agents.sh setup`.

## What breaks first in production

1. **SQLite write contention.** There is one writer at a time, and blocking
   database calls run inside async handlers, so a held lock stalls every
   request.
2. **Notices stuck in `processing`.** A crashed worker leaves them claimed,
   and nothing reclaims them.
3. **Malformed but signed bodies return 500**, and the vendor retries
   forever.
4. **Secrets.** There is one plaintext secret per tenant, no replay
   protection and no key rotation.
5. **Extraction on real notices.** The regex extractor fits the synthetic
   format only.

## Notes

- **Pushes.** The brief asks for a push after each phase; I pushed once, at
  the end.
- **Mistakes during the build**, including my own, are listed in
  [evidence/incidents.md](evidence/incidents.md).
- **Known limit.** The path guard checks command text; it is not an OS
  sandbox. The two separations rely on blind roles being unable to run
  code, not on the guard ([docs/permissions.md](docs/permissions.md)).
