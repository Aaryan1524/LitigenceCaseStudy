# Litigence Parallel Filings

A multi-tenant docket service, built by several coding agents working in
parallel: signed court-filing webhooks, an extraction worker and a review
API over one SQLite database. I directed the agents and checked their
work. This README explains how I ran it and how I evaluated what they
produced.

## How I approached it

I treated the agents like a contractor team I couldn't fully trust:

1. Agree the spec in writing before any code exists.
2. Give each agent only what it needs to do its job.
3. Let machines, not the agents, decide when work is done.
4. Have every piece checked by someone other than its author.
5. Keep a record good enough to prove all of this afterwards.

## Setup

- **One contract.** [docs/contract.md](docs/contract.md) fixes the schema,
  the statuses, the function signatures and the response for every HTTP
  case. Agents build against it, never against each other's code.
- **One file per role.** [.claude/agents/](.claude/agents/) sets each
  agent's model, tools and a short prompt.
  [tasks/](tasks/) and [plans/](plans/) give each agent its job, an
  acceptance check and the steps to get there.
- **Small context.** [scripts/packs.py](scripts/packs.py) builds one file
  per agent ([context/](context/)), with only the parts of the contract
  that agent uses. Most are 600 to 1,000 words.
- **Isolation.** Each agent runs as its own session in its own git clone,
  on its own branch, with only its own files on disk. It has no network
  tools, no access to the contract or hooks, and nothing outside its
  folder. Each setting and the reason for it is in
  [docs/permissions.md](docs/permissions.md).
- **Rules enforced by code.**
  - A hook ([path_guard.py](.claude/hooks/path_guard.py)) checks every file
    and command an agent tries to use.
  - A stop hook ([gate.py](.claude/hooks/gate.py)) won't let an agent
    finish with uncommitted work, files outside its slice, or code that
    doesn't import.

Before any build work, I tested the guard with real agent sessions trying
to break out ([evidence/phase1-guard-test.md](evidence/phase1-guard-test.md)).

## Running the agents

| Agent | Built | Model |
|---|---|---|
| api | intake webhook, review API, database | Opus |
| worker | extraction loop and answer checking | Opus |
| extract | the text parser | Haiku |
| tests | the test suite, from the contract only | Opus |
| evals-data | 20 labelled sample notices | one model call, no tools |
| reviewer | read the finished code | Opus |

extract, api and tests started together. The worker started automatically
when api committed "db ready". The eval data was written only after
extract had finished. I merged each agent's branch into `main` as it
landed ([docs/runbook.md](docs/runbook.md) has the exact commands).

## How I evaluated the work

**1. Per-agent checks.** Each agent had to pass its own acceptance check
and the stop hook before it could finish. For example, the worker had to
show that two workers racing over 200 notices processed each one exactly
once.

**2. Tests from an agent that couldn't see the code.** The tests agent
wrote 143 tests from the contract alone. It had no copy of the code and no
way to run anything; I ran its tests and sent back only pass/fail results.
All 143 passed on the first integration.

**3. Evals.** 20 labelled notices ran through the same checking code the
worker uses. They include a matter that belongs to the other firm, an
impossible date and a notice that tries to inject instructions. The result
was 1.00 on every field.

**4. A fresh reviewer.** A reviewer agent that had written nothing read the
integrated code and raised 5 findings. I had the owning agents fix the two
that mattered: a database error was being saved as an invalid answer,
silently losing data, and a bad signature header returned 500 instead of
403. I deferred the other three, with reasons
([evidence/phase3-review.md](evidence/phase3-review.md)).

**5. Breaking a protection on purpose.** I had an agent remove the
raw-bytes signature check. 7 tests failed, including the brief's own
signed example. Its revert brought everything back to green
([evidence/phase3-demo.md](evidence/phase3-demo.md)).

**6. A second, independent test suite.** I moved the original tests aside
and had Codex write a new suite and eval set. It saw the code and contract
but none of the original tests or labels. Then I ran each suite against
the other's deliberate defects:

| | Original suite | Codex suite (on `main`) |
|---|---|---|
| Tests | 156 passed | 160 passed |
| Evals | 1.00 per field | 100% per field |
| Catches the other's 7 deliberate defects | 7 / 7 | 7 / 7 |

**7. Proof of who did what.**
- Every commit is stamped with the agent's role and session by a git hook
  the agents couldn't reach.
- Every tool call went to a log in which each line is chained to the
  previous one by hash.
- [scripts/audit.py](scripts/audit.py) checks that no agent's git history
  ever held files it wasn't allowed to see. Each check has a negative test
  that shows it can fail.

Results: [evidence/audit.md](evidence/audit.md).

## Keeping agents apart

Two pairs had to stay blind to each other.

- **Tests and code.** The tests agent's folder never contained the code,
  and it could not run anything. Its log shows every file it read.
- **The parser and the eval data.**
  - The eval data came from a single model call with no tools at all.
  - A script made sure the parser was finished before the eval data
    existed anywhere on disk.
  - The audit confirms neither side's files entered the other's git
    history.

## When things changed or went wrong

- **The spec changed three times.** Each change went into the contract
  first, then to the affected agents. One came from an agent: it found
  seed data missing from its context and stopped to ask, instead of
  inventing it. The change log is at the end of
  [docs/contract.md](docs/contract.md).
- **I made mistakes too.** My stop hook once blamed an agent for files I
  had merged in, and one of my merges let code into the tests agent's git
  history. It was never on disk and the agent couldn't run it, but the
  audit still flags it. Each mistake, and what it changed, is in
  [evidence/incidents.md](evidence/incidents.md).
- **The guard is not a full sandbox.** It checks commands as text, so the
  separations don't rely on it. They rely on the blind agents having no
  way to run code.

## What I'd expect to break first in production

1. SQLite under concurrent writes. Blocking database calls inside async
   handlers stall every request.
2. Notices stuck mid-processing after a worker crash, with nothing to
   recover them.
3. Malformed but validly signed requests return 500, so the vendor retries
   forever.
4. One plaintext secret per firm, no replay protection and no key
   rotation.
5. The regex parser on real court notices.

## Run it

```bash
pip install -r requirements.txt
python scripts/run_checks.py      # tests (including signed webhook → worker → approve → list) and evals
python scripts/mutation_check.py  # 7 deliberate defects, each must be caught
python scripts/cross_check.py     # the original suite against the same code and defects
```
