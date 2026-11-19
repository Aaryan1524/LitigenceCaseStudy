<div align="center">
  <h1>Litigence Parallel Filings</h1>
  <h3>Coding agents run like an untrusted contractor team: a written
  contract, sealed workspaces, machine-checked hand-offs, and proof of
  who wrote what.</h3>
  <img src="https://img.shields.io/badge/independent%20tests-160%20passing-brightgreen" alt="Independent tests: 160 passing">
  <img src="https://img.shields.io/badge/evals-100%25-brightgreen" alt="Evals: 100%">
  <img src="https://img.shields.io/badge/defect%20probes-7%2F7%20caught-2E7D32" alt="Defect probes: 7 of 7 caught">
  <img src="https://img.shields.io/badge/agent%20cost-%246.02-blue" alt="Agent cost: $6.02">
</div>

<br>

The brief (`parallel-filings-brief.md`) is a multi-tenant docket
service: signed webhooks, an extraction worker and a review API on
SQLite. It is judged on **how the agents are set up, directed and
checked**. Five agents and one no-tools LLM call built it in parallel.
The tests and evals on `main` were then written separately, by Codex.

## Results

| | Build-pipeline suite | Codex suite (on `main`) |
|---|---|---|
| Written by | tests agent, which could not read or run the code | Codex, with no access to our tests or eval labels |
| Tests | 156 passed | **160 passed** |
| Evals (20 notices) | 1.00 per field | **100% per field, 100% exact match** |
| Catches the other suite's 7 deliberate defects | **7 / 7** | 7 / 7 |
| Eval notices shared between the two sets | 0 | 0 |

```bash
pip install -r requirements.txt
python scripts/run_checks.py      # 160 tests + evals + source hash check
python scripts/mutation_check.py  # 7 deliberate defects, all caught
python scripts/cross_check.py     # the build-pipeline suite on the same code, against the same 7 defects
```

## The approach

```
              ARCHITECT: contract · context packs · merges · decisions
                       (the only channel; agents never talk to each other)
     ┌───────────┬──────────────┼───────────────┬────────────────┐
  extract       api           tests          evals-data        worker
  Haiku         Opus          Opus, can't    one LLM call,     Opus, starts on
                              run code       no tools          api's "db ready"
     └───────────┴── Stop gate: clean · in-slice · imports ─────┘
                                │
     main ← merge ← tests ← fresh reviewer ← audit (evidence/audit.md)
                                │
                  Codex: an independent suite, cross-checked
```

## What's different

| Usual approach | Here |
|---|---|
| Helpers share one checkout | Each agent is a separate `claude` process in **its own git clone**. A sparse checkout puts only its slice on disk |
| Roles are prompts | **Roles are files**: `.claude/agents/<role>.md` sets the model, tools and prompt. The small job ran on Haiku for $0.01 |
| Every agent reads the whole spec | **Context packs**: 600 to 1,000 words per agent (`scripts/packs.py`) |
| "Don't look at the evals" | **Blind roles can't execute code.** evals-data is one call with `--tools ""`. Run order is enforced by script |
| The agent says "done" | **A Stop hook decides**: clean tree, only its own files, modules import |
| "Nobody peeked, trust me" | **Content-hash proof**: forbidden blobs never entered a clone's git store. Every check has a negative control |
| Unattributed commits | **Every commit is stamped** `Agent-Role` and `Agent-Session` by a hook agents can't reach. Every tool call goes to a hash-chained log |
| The same model writes the code and its tests | **Three independent sources**: build agents, a code-blind tests agent, and a Codex suite. Each is cross-checked against the others' defects |

## How it ran

1. **Parallel build.** extract, api and tests started together. evals-data ran
   only after extract ended. worker launched automatically when api committed
   "db ready".
2. **First integration.** 143 tests, written blind, passed against code
   written by agents that never saw them.
3. **Mid-build change.** An agent found a gap in the contract and stopped
   instead of guessing. The contract was amended and the change pushed to
   that agent.
4. **Review.** A fresh reviewer raised 5 findings. 2 were fixed by the
   agents that own the code (a DB error that silently lost data; a 500
   instead of 403); 3 were deferred with reasons.
5. **Demo.** An agent removed the raw-bytes signature check. 7 tests
   failed. Its own revert restored a full pass.

| Role | Model | Context words | Cost | Minutes |
|---|---|---|---|---|
| extract | Haiku | 596 | $0.01 | 0.4 |
| api | Opus | 1,000 | $1.92 | 2.3 |
| worker | Opus | 1,019 | $1.49 | 3.2 |
| tests | Opus | 2,890 | $2.11 | 4.6 |
| evals-data | Opus, no tools | 653 | $0.11 | 0.5 |
| reviewer | Opus | 2,434 | $0.38 | 1.2 |

## Incidents, kept in the record

1. A lean context pack missed the seed data. The agent asked instead of
   inventing it, and the contract was fixed.
2. The Stop gate blamed the worker for merged files. The agent refused to
   tamper, and the gate was fixed.
3. The evals-call save failed. It was recovered without a second model call.
4. Code reached the tests clone's git history through a contaminated
   contract branch. It was never on disk, and the agent cannot run code.
   The audit still flags it, and `amend` now refuses this.

Details: [evidence/incidents.md](evidence/incidents.md).

## What breaks first in production

1. **SQLite write contention.** Blocking calls inside async handlers stall
   every request.
2. **Notices stuck in `processing`.** A crashed worker is never recovered.
3. **Malformed but signed bodies return 500**, and the vendor retries
   forever.
4. **One plaintext secret per tenant.** There is no nonce, so requests can
   be replayed, and no key rotation.
5. **Regex extraction on real notices.** It needs a model behind the same
   `check()`.

## Read next

- [docs/contract.md](docs/contract.md): the single source of truth and its
  change log.
- [docs/permissions.md](docs/permissions.md): every flag, permission and
  hook, with the reason for each.
- [docs/runbook.md](docs/runbook.md): the exact orchestration commands.
- [evidence/audit.md](evidence/audit.md): stamps, fingerprints, log chains,
  timeline.
- [reports/RESULTS.md](reports/RESULTS.md): the Codex evaluation.
  [evidence/cross-check.json](evidence/cross-check.json): both suites
  against each other's defects.

## Layout

```
.claude/agents/   role definitions        scripts/agents.sh   orchestrator
.claude/hooks/    guard, Stop gate, logs  scripts/audit.py    provenance audit
context/          one pack per role       app/ worker/ extractor/   built by agents
docs/             contract, permissions   tests/ evals/ reports/    Codex suite
evidence/         audit, logs, transcripts, clone bundles
```

**Timeline:** Phase 1 setup, 16:49 to 17:05. Agents built and reviewed
the system 18:03 to 18:20, after the live hour, at the interviewer's
invitation.
