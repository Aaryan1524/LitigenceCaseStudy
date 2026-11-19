<div align="center">
  <h1>Litigence Parallel Filings</h1>
</div>

<div align="center">
  <h3>Coding agents treated as an untrusted contractor team: a written
  contract, least-privilege workspaces, machine-checked hand-offs, and a
  provenance record you can verify yourself.</h3>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/independent%20tests-160%20passing-brightgreen" alt="Independent tests: 160 passing">
  <img src="https://img.shields.io/badge/independent%20evals-100%25-brightgreen" alt="Independent evals: 100%">
  <img src="https://img.shields.io/badge/defect%20probes-7%2F7%20caught%20by%20both%20suites-2E7D32" alt="Defect probes: 7 of 7 caught by both suites">
  <img src="https://img.shields.io/badge/agents-5%20%2B%201%20no--tools%20call-6A5ACD" alt="Agents: 5 plus 1 no-tools call">
  <img src="https://img.shields.io/badge/every%20commit-role%20%2B%20session%20stamped-2E7D32" alt="Every commit stamped with role and session">
  <img src="https://img.shields.io/badge/separations-checked%20by%20content%20hash-0B7285" alt="Separations checked by content hash">
  <img src="https://img.shields.io/badge/agent%20cost-%246.02-blue" alt="Agent cost: $6.02">
</div>

<br>

This is my submission for the Litigence live exercise
(`parallel-filings-brief.md`). The brief judges how coding agents are set
up, directed and checked, so this README is about the **approach**. The
product is a multi-tenant docket service: signed webhooks, an extraction
worker and a review API over one SQLite file. It is the ground the
agents worked on.

## Results: two suites that never saw each other

The tests and evals on `main` were **written by a different AI**, not by
the agents that built the system. It was given a code-only export of
`main`: `app/`, `worker/`, `extractor/`, the contract and the brief, with
no git history, no evidence and none of the original tests or eval
labels. So the same model family never grades its own homework.

| | Original suite (build agents) | Independent suite (different AI) |
|---|---|---|
| Who wrote it | the tests agent in this pipeline | a separate AI, outside the pipeline |
| Saw the implementation | **no**: it could not read or run the code | yes: it read the code, by its own account |
| Saw the other suite | no | no: it reports it did not retrieve the original tests or labels |
| Tests on the same code | 156 passed | **160 passed** |
| 20-notice evals | 1.00 on every field | **100% on every field, 100% exact match** |
| Eval texts shared between the two sets | 0 | 0 |
| Its own defect probes | 1 (an agent-made `DEMO:` commit) | 7 mutations, all detected |
| **Catches the other side's 7 defects** | **7 / 7** | 7 / 7 |
| Where it lives | branches `feat/tests`, `feat/evals-data` | `tests/`, `evals/`, `reports/` on `main` |

Neither suite found an application defect. The cross-check is the
strongest signal here: the suite written without ever seeing the code
caught every defect the code-reading evaluator designed. Those include
signing re-serialized JSON, cross-tenant matter lookup, reclaiming a
claimed notice, a non-transactional approve, swallowed database errors
and accepting impossible dates.

Reproduce all of it:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/run_checks.py       # 160 passed; evals 100%; app files match the evaluated hashes
.venv/bin/python scripts/mutation_check.py   # 7/7 selected defects detected
.venv/bin/python scripts/cross_check.py      # original suite on the same code + the 7 defects against it
```

Reports from the evaluator are in [reports/RESULTS.md](reports/RESULTS.md)
and [reports/INDEPENDENT-EVAL.md](reports/INDEPENDENT-EVAL.md). The
cross-check output is in [evidence/cross-check.json](evidence/cross-check.json).
Both suites cover the synthetic contract only. They don't measure
extraction quality on real court notices, sustained load or crash
recovery.

## The approach in one picture

```
                 ARCHITECT  (contract · context packs · merges · decisions)
                                     │  the only channel; agents never talk to each other
      ┌────────────┬─────────────────┼──────────────────┬──────────────────┐
   extract        api              tests            evals-data          worker
   Haiku          Opus             Opus             one LLM call        Opus
   596-word pack  1,000-word pack  full contract    no tools at all     starts on api's
                                   cannot run code  runs after extract  "db ready" commit
      │            │                 │                  │                  │
      └────────────┴── Stop gate: clean tree · only own files · imports ───┘
                                     │
               main  ←  merge  ←  test run  ←  fresh reviewer (read-only clone)
                                     │
                          audit  →  evidence/audit.md
```

## What makes it different

| Common approach | This repo |
|---|---|
| One session spins up helper agents that share a checkout | Every agent is a separate headless `claude` process in **its own git clone**: its own object store, no remote, and a sparse checkout that puts only its slice on disk |
| Roles live in prompts | **Roles are versioned files** (`.claude/agents/<role>.md`): model, tool list, three-line prompt. The cheap job ran on Haiku for $0.01 |
| Every agent reads the whole spec | **Context packs**: `scripts/packs.py` gives each agent one file with its task, its plan and only the contract sections it needs |
| "Don't look at the evals" written in `CLAUDE.md` | **Agents that must stay blind cannot execute code.** evals-data is one LLM call with `--tools ""` (1 turn, 0 tool calls). The tests agent has no python or pytest. The order is enforced by script |
| Agent says "done" | **A Stop hook decides "done"**: clean tree, every committed file inside the agent's slice, modules import. Contract and merge commits are excluded so agents are not blamed for the architect's work |
| The same AI writes the code and the tests that grade it | **Three independent sources**: build agents wrote the code; a tests agent blind to the code wrote one suite; a different AI wrote a second suite and the evals without seeing the first. The two suites are cross-checked against each other's defects |
| "Trust me, nobody peeked" | **Proof from git's content hashes**: the audit checks that the forbidden files' blobs never entered a clone's object store, with negative controls showing the check can fail |
| Logs, if any | **Hash-chained logs** of every tool call, allowed or denied. Editing or deleting a line breaks the chain, and the audit shows it does |
| Who wrote this line? | **Every agent commit is stamped** `Agent-Role` and `Agent-Session` by a git hook the agent cannot reach. One session id links transcript, logs, commits and timeline |
| Spec changes by chat message | **Changes go through a `contract` branch** that never carries code, so a mid-build change cannot leak one agent's work to another |

## How the build actually ran

Times come from `evidence/sessions.log`.

1. **18:03, extract.** It ran alone first, as the verification run. The
   init event confirmed the agent file was honoured: Haiku, its listed
   tools only, zero MCP servers. Result: 2 stamped commits, gate passed,
   23 seconds.
2. **18:04, api and tests in parallel.**
3. **18:05, evals-data.** One no-tools call, which the script allows
   only because extract had ended. Extract is frozen from that moment.
4. **18:06, api stopped at a gap in my contract.** Its lean pack said
   "seed the fixtures from the brief" but did not contain the brief. It
   reported the gap instead of inventing tenants. I amended the contract,
   regenerated the packs, merged the fix into the agent's clone and
   resumed the session. That was the requirement-change path, used for
   real.
5. **18:07, worker.** Launched by a watcher the moment api committed
   `CHECKPOINT: db ready`.
6. **18:09, first integration.** The 143 tests, written blind by the
   tests agent, passed against code written by agents that never saw
   them.
7. **Review.** A fresh reviewer agent in a read-only clone raised 5
   findings. Two were fixed by the agents that own that code, through
   contract amendments:
   - a database error was being stored as an invalid answer, silently
     losing good data;
   - a non-ASCII signature header returned 500 instead of 403.

   Three were deferred with reasons
   ([evidence/phase3-review.md](evidence/phase3-review.md)).
8. **Demo.** The api agent made a `DEMO:` commit computing the signature
   over `json.dumps` instead of the raw bytes. 7 tests failed, including
   the brief's signed example. Its own revert restored a full pass
   ([evidence/phase3-demo.md](evidence/phase3-demo.md)).

### Agent scorecard (lean slices)

| Role | Model | Pack words | Tool calls | Guard denials | Cost USD | Minutes |
|---|---|---|---|---|---|---|
| extract | Haiku | 596 | 13 | 3 | 0.01 | 0.4 |
| api | Opus | 1,000 | 28 | 3 | 1.92 | 2.3 |
| worker | Opus | 1,019 | 50 | 5 | 1.49 | 3.2 |
| tests | Opus | 2,890 | 23 | 2 | 2.11 | 4.6 |
| evals-data | Opus, no tools | 653 | 0 | 0 | 0.11 | 0.5 |
| reviewer | Opus | 2,434 | 14 | 0 | 0.38 | 1.2 |

$6.02 in total for the agent sessions. That excludes the orchestrating
session and the Phase 1 guard probes. Most denials were an agent's
first-move habit: `cat .claude/role`, or `git -C <absolute path>`.

## The two separations, and how each is shown

| Separation | How it is enforced | How it is shown |
|---|---|---|
| `extract` vs `evals/notices.jsonl` | evals-data is a no-tools call run from an empty temp directory. extract refuses to start while any `notices.jsonl` exists; evals-data refuses until extract has ended | No `evals/` blob in extract's object store, and no `extractor/` blob in evals-data's. The session timeline. The call record: `num_turns: 1` |
| tests vs code | The tests agent cannot run code, its clone never received `main`, and it only ever got test ids and one-line messages back | Guard-log read-before-write check; clean-tree check for conftest side effects; fingerprints (one ❌, see incident 4) |

Every audit check has a negative control. The fingerprint check reports
the blob present when pointed at a repo that does hold it, and the chain
check reports a log with one byte changed as broken.

## Incidents, kept in the record

These were found during the build. Showing them is part of the approach:
the evidence is only worth something if it can also show what went
wrong. Full detail is in [evidence/incidents.md](evidence/incidents.md).

1. **The lean pack missed the seed fixtures.** The agent stopped and asked
   instead of guessing. I fixed the contract.
2. **My Stop gate blamed the worker for files it didn't write**, after a
   sync. The agent refused to tamper with anything and explained the
   cause. I fixed `sync` and re-ran the gate myself; that run is logged
   with an empty session id, because the agent didn't run it.
3. **My evals-call script failed to save its output.** I recovered
   without a second model call, so the record stays at one call.
4. **I merged code into the `contract` branch by mistake.** The next
   amend put 3 code blobs into the tests clone's git history. They were
   never on disk, the agent cannot run code, and its log shows it only
   read its own pack and committed. The fingerprint check still reports
   ❌. I left it that way and made `amend` refuse a contract branch that
   carries code.

## What would break first in production

1. **SQLite write contention.** There is one writer at a time, and
   blocking calls run inside an async handler, so one held lock stalls
   every request.
2. **Notices stuck in `processing`.** Nothing recovers a crashed worker
   (out of scope by the brief).
3. **Malformed but validly signed bodies return 500.** The vendor then
   retries forever.
4. **The signature scheme.**
   - There is one shared secret per tenant, in plain text, in the same
     database.
   - There is no timestamp or nonce, so a captured request can be
     replayed forever.
   - There is no key rotation.
5. **Extraction on real notices.** The extractor follows fixed text
   conventions. Real notices need a model behind the same code-level
   `check()`.

---

## Read next

- **[docs/contract.md](docs/contract.md)**: the single source of truth,
  with a change log of every amendment made during the build.
- **[docs/permissions.md](docs/permissions.md)**: every launch flag,
  permission and hook, with the reason for each, plus the known limits.
- **[docs/runbook.md](docs/runbook.md)**: the exact command order.
- **[evidence/audit.md](evidence/audit.md)**: stamps, fingerprints,
  chains, timeline and scorecard.
- **[evidence/](evidence/)**: transcripts, logs, the session timeline and
  clone bundles for independent checks.

## Layout

```
LitigenceAI/
├── parallel-filings-brief.md   the original brief
├── CLAUDE.md                   rules every agent loads
├── docs/                       contract, permissions, runbook
├── context/                    one generated pack per role
├── tasks/  plans/              per-role task (what + acceptance) and plan (how)
├── .claude/
│   ├── agents/                 role definitions: model, tools, prompt
│   ├── hooks/path_guard.py     PreToolUse: per-role file and command allowlist
│   ├── hooks/gate.py           Stop: clean tree, in-slice commits, imports
│   ├── hooks/chainlog.py       hash-chained, lock-protected log writer
│   ├── roles.json              per-role checkout, read, write, bash, gate
│   ├── agent-settings.json     permissions passed to every agent
│   └── skills/worker-pipeline/ worker skill: SKILL.md, references, examples, scripts
├── scripts/
│   ├── agents.sh               orchestrator (setup run resume evals-call amend sync collect audit)
│   ├── packs.py                builds context/<role>.md from contract sections
│   ├── audit.py                writes evidence/audit.md
│   ├── run_checks.py           independent tests + evals + hash check   (independent evaluator)
│   ├── mutation_check.py       7 deliberate defects in disposable copies (independent evaluator)
│   └── cross_check.py          both suites on the same code, and the 7 defects against the original
├── app/  worker/  extractor/   the application, written by the api, worker and extract agents
├── tests/  evals/              the independent suite and eval set (a different AI)
├── reports/                    the independent evaluator's results, hashes and environment
└── evidence/                   audit, incidents, logs, transcripts, clone bundles, cross-check
```

## Try it

**The product, by hand:**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export LITIGENCE_DB=/tmp/litigence.db
.venv/bin/uvicorn --factory app.main:create_app --port 8000 &
printf '%s' '{"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example","text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply."}' > /tmp/body.json
curl -s -X POST localhost:8000/webhooks/notices -H 'content-type: application/json' \
  -H 'X-Signature: 4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2' \
  --data-binary @/tmp/body.json                                     # 200
.venv/bin/python -m worker --once                                   # processed 1
curl -s -X POST localhost:8000/tenants/alderbrook-law/notices/NTC-8841/approve   # 200
curl -s localhost:8000/tenants/alderbrook-law/notices               # status docketed
```

**The provenance, from this repo alone:**

```bash
# Every agent commit names its role and session
git log --all --format='%h %<(10,trunc)%(trailers:key=Agent-Role,valueonly,separator=) %<(9,trunc)%(trailers:key=Agent-Session,valueonly,separator=) %s' | grep -v '^[0-9a-f]* *  '

# extract's history never held the eval data
git clone -q evidence/clones/extract.bundle /tmp/ex && \
  git -C /tmp/ex cat-file -e $(git rev-parse feat/evals-data:evals/notices.jsonl) 2>/dev/null \
  && echo HELD || echo "never held notices.jsonl"

# the tool-call logs are unedited
python3 -c "import sys,glob; sys.path.insert(0,'.claude/hooks'); import chainlog; \
  [print(f, chainlog.verify(f)) for f in sorted(glob.glob('evidence/logs/*.log'))]"
```

**The orchestration** (needs the `claude` CLI): see
[docs/runbook.md](docs/runbook.md). It starts with
`scripts/agents.sh setup`, which creates the clones in `../litigence-agents`.

## Known limits

- **The guard reads command strings; it is not a sandbox.** A role that
  can run Python could read a sibling folder at runtime. The two
  separations do not depend on the guard: the blind roles cannot execute
  code, and the eval data never existed on disk while extract ran. In
  production, run each agent in a sandboxed session with no network.
- **No OS-level network block** for the roles that run Python. They have
  no network tools and no credentials.
- **The bundles hold reachable history only.** The full object-store
  check ran locally; see `evidence/audit.md`.

## Timeline

- **Phase 1 setup:** commits 16:49 to 17:05.
- **Orchestration upgrade:** 18:03.
- **Phases 2 and 3, run by the agents:** 18:03 to 18:20, finished after
  the live hour at the interviewer's invitation.
- **Original tests and evals moved off `main`**, so a different AI could
  write an independent suite. The independent suite and evals are now on
  `main`; the originals remain on `feat/tests` and `feat/evals-data`.
- **Push:** once, at the end, not after each phase.

## Architecture history

1. **Worktrees → separate clones.** A shared object store let `git show`
   read other branches.
2. **Prompt rules → guard hook.** "Don't read X" is not evidence; a
   logged denial is.
3. **Guard alone → blind roles cannot run code.** A real session showed
   Python getting past the guard with a runtime path.
4. **Interactive agents → headless sessions with ids.** One id ties
   transcript, logs, commits and timeline together.
5. **Full contract per agent → generated context packs.** Each agent
   reads 600 to 1,000 words, instead of about 2,700.
6. **Trust "done" → Stop gate.** An agent can't finish with stray edits
   or broken imports.
7. **Plain logs → hash-chained logs, and an audit with negative
   controls.** The evidence can be checked, and the checks are shown to
   fail when they should.
8. **One test suite → two independent suites, cross-checked.** A
   different AI wrote the tests and evals on `main` from a code-only
   export. Each suite was then run against the other side's deliberate
   defects.
