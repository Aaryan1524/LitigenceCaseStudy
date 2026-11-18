<div align="center">
  <h1>Litigence Parallel Filings</h1>
</div>

<div align="center">
  <h3>Six AI agents built a multi-tenant docket service in parallel, and
  every line traces back to the agent and session that wrote it, with
  each separation check and its result shown.</h3>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/tests-156%20passing-brightgreen" alt="Tests: 156 passing">
  <img src="https://img.shields.io/badge/evals-1.00%20on%20every%20field-brightgreen" alt="Evals: 1.00 on every field">
  <img src="https://img.shields.io/badge/agents-5%20%2B%201%20no--tools%20call-6A5ACD" alt="Agents: 5 plus 1 no-tools call">
  <img src="https://img.shields.io/badge/agent%20cost-%246.02-blue" alt="Agent cost: $6.02">
  <img src="https://img.shields.io/badge/deps-fastapi%20uvicorn%20httpx%20pytest-lightgrey" alt="Dependencies: fastapi, uvicorn, httpx, pytest">
</div>

<br>

This is my submission for the Litigence live exercise
(`parallel-filings-brief.md`). It has two parts:

- **The product:** signed court-filing webhooks, an extraction worker,
  and a review API over one SQLite file, shared by two law firms.
- **The process (what's being judged):** how I set up, directed and
  checked the agents that wrote it. I wrote no application or test code.
  Every agent ran in its own clone with a context pack holding only its
  slice of the contract. A guard hook and a stop gate enforced the rules,
  and an audit checks the two no-peeking separations against git's own
  content hashes. Every check passed except one, which is caused by my
  own mistake (incident 4) and is explained below.

```bash
pip install -r requirements.txt && pytest && python -m evals
# 156 passed, 1 warning
# filing_type 20/20 = 1.00 ok · matter_id 20/20 = 1.00 ok · filed_date 20/20 = 1.00 ok
```

> [!NOTE]
> **Timeline, from the commits.**
> - **Phase 1 setup:** commits 16:49 to 17:05.
> - **Orchestration upgrade:** 18:03.
> - **Phases 2 and 3, run by the agents:** 18:03 to 18:20. These were
>   finished after the live hour, at the interviewer's invitation.
> - **Push:** the repo was pushed once, at the end, not after each phase.
>
> Every agent session's start and end time is in
> `evidence/sessions.log`, and every commit carries its timestamp.

## Why this approach?

- **Contract first, agents second.** Every agent builds against
  `docs/contract.md`, never against another agent's code. The contract
  has the schema, the statuses, the function signatures and every HTTP
  response.
- **Roles are files, not prompts.** Each role is defined in
  `.claude/agents/<role>.md`: its model, its tools and a three-line
  system prompt. extract ran on Haiku for $0.01. The others ran on Opus.
- **Lean context.**
  - `scripts/packs.py` gives each agent one file, `context/<role>.md`,
    with only its task, its plan and the contract sections it needs:
    596 words for extract, against 2,890 for the tests agent, which
    must see everything.
  - Each clone's sparse checkout puts only that role's files on disk.
- **Separations are physical, then proven.**
  - The two blind roles cannot run code. evals-data is a single LLM
    call with no tools, and tests has no python or pytest.
  - Extract and evals-data run in a strictly enforced order.
  - The audit checks each clone's git object store for the forbidden
    content hashes.
- **Machines accept the work, not trust.**
  - A Stop hook refuses to let an agent finish with uncommitted work,
    files outside its slice, or modules that don't import.
  - Tests come from a different agent than the code.
  - A fresh reviewer reviews the integrated code.
- **Every action is traceable.**
  - Each agent commit is stamped `Agent-Role` and `Agent-Session` by a
    git hook the agent cannot reach.
  - Every tool call goes to a hash-chained log, so an edited or deleted
    line is detectable.
  - The session id ties transcript, logs, commits and timeline together.

```
            architect: contract, packs, merges, decisions
                              │
     ┌──────────┬─────────────┼──────────────┬─────────────┐
   extract     api          tests        evals-data      worker
   (Haiku)   (Opus)    (Opus, blind:    (one call,    (Opus, starts
     │          │       cannot run      no tools,      at "db ready")
     │          │       code)           after extract)      │
     └──────────┴──── Stop gate: clean, in-slice, imports ──┘
                              │
          main ← merge ← pytest + evals ← reviewer (fresh, read-only)
                              │
                      audit → evidence/audit.md
```

Workers never talk to each other. The architect is the only channel, and
that is what keeps information from leaking between agents.

---

## Documentation

- **[docs/contract.md](docs/contract.md)**: the single source of truth,
  with a change log of every amendment made during the build.
- **[docs/permissions.md](docs/permissions.md)**: every launch flag,
  allow and deny rule, and hook, with the reason for each. Also how each
  separation holds, and the known limits.
- **[docs/runbook.md](docs/runbook.md)**: the exact command order for
  build, contract changes and review.
- **[evidence/audit.md](evidence/audit.md)**: the provenance audit, with
  stamps, fingerprints, chains, timeline and scorecard.
- **[evidence/incidents.md](evidence/incidents.md)**: four things that
  went wrong, and what each one changed.
- **[evidence/phase3-review.md](evidence/phase3-review.md)** and
  **[evidence/phase3-demo.md](evidence/phase3-demo.md)**: the review
  findings, the decisions on them, and the protection-removal demo.

## Directory layout

```
LitigenceAI/
├── parallel-filings-brief.md   the original brief
├── CLAUDE.md                   rules every agent loads
├── docs/                       contract, permissions, runbook
├── context/                    one generated pack per role (scripts/packs.py)
├── tasks/  plans/              per-role task (what + acceptance) and plan (how)
├── .claude/
│   ├── agents/                 role definitions: model, tools, prompt
│   ├── hooks/path_guard.py     PreToolUse: per-role file and command allowlist
│   ├── hooks/gate.py           Stop: clean tree, in-slice commits, imports
│   ├── hooks/chainlog.py       hash-chained, flock-protected log writer
│   ├── roles.json              per-role checkout, read, write, bash, gate
│   ├── agent-settings.json     permissions passed to every agent
│   └── skills/worker-pipeline/ worker skill: SKILL.md, references, examples, scripts
├── scripts/
│   ├── agents.sh               orchestrator (setup run resume evals-call amend sync collect audit)
│   ├── packs.py                builds context/<role>.md from contract sections
│   └── audit.py                writes evidence/audit.md
├── app/                        intake, approve, list, db            (api agent)
├── worker/                     check, run_extraction, run_once      (worker agent)
├── extractor/                  extract(text)                        (extract agent)
├── evals/                      __main__.py (worker), notices.jsonl  (evals-data call)
├── tests/                      156 tests                            (tests agent)
└── evidence/                   audit, incidents, logs, transcripts, clone bundles
```

### Why separate clones instead of worktrees

Worktrees share one object store. A worktree's agent can run
`git show feat/evals-data:evals/notices.jsonl` and read a file that was
never on its disk. Each agent therefore gets its own clone (`--no-hardlinks`,
remote removed) and a no-cone sparse checkout from `.claude/roles.json`.
`agents.sh collect` brings each branch back into this repo.

### Why the blind roles cannot run code

The guard reads command strings; it is not a sandbox. Any role that can
run Python can build a path at runtime and read a sibling folder. A real
session proved this (probe 10 in `evidence/phase1-guard-test.md`). So
the roles that must stay blind cannot execute anything:

- **evals-data** is one `claude -p --tools ""` call, run from an empty
  temp directory. It took one turn, with no tool round-trips.
- **tests** gets no python or pytest. I run its collection check, and it
  only ever receives test ids and one-line messages (`--tb=no`).

On top of that, `agents.sh` enforces the order:
- extract refuses to start if any `notices.jsonl` exists on disk;
- evals-data refuses to start until extract has ended;
- extract is frozen afterwards.

### Why the contract branch never carries code

Mid-build changes reach agents by merging the `contract` branch into
their clones. That branch may only hold docs, packs, config and scripts.
I broke this rule once, by fast-forwarding `contract` to `main`. The next
`amend` put three code blobs into the tests clone's git history
([incident 4](evidence/incidents.md)). `amend` now refuses any contract
branch that has ever carried a code path, and the audit checks for it.

## Reproduce

### 1. The product

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest                          # 156 passed, 1 warning
.venv/bin/python -m evals                 # 1.00 on filing_type, matter_id, filed_date
```

### 2. One end-to-end path by hand

```bash
export LITIGENCE_DB=/tmp/litigence.db
.venv/bin/uvicorn --factory app.main:create_app --port 8000 &
printf '%s' '{"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example","text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply."}' > /tmp/body.json
curl -s -X POST localhost:8000/webhooks/notices -H 'content-type: application/json' \
  -H 'X-Signature: 4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2' \
  --data-binary @/tmp/body.json                                   # 200
.venv/bin/python -m worker --once                                 # processed 1
curl -s -X POST localhost:8000/tenants/alderbrook-law/notices/NTC-8841/approve   # 200
curl -s localhost:8000/tenants/alderbrook-law/notices             # status docketed
```

### 3. The orchestration

This step needs the `claude` CLI. The clones go in `../litigence-agents`.

```bash
scripts/agents.sh setup                       # clones, sparse slices, stamp hooks, venv
HEADLESS=1 scripts/agents.sh run extract      # then api and tests, in parallel
scripts/agents.sh evals-call                  # refuses until extract has ended
HEADLESS=1 scripts/agents.sh run worker       # after api commits "CHECKPOINT: db ready"
scripts/agents.sh collect && scripts/agents.sh audit
```

The full order, including merges, is in [docs/runbook.md](docs/runbook.md).

## Verify the separations yourself

The audit ran against the agents' full object stores on my machine. The
results are in [evidence/audit.md](evidence/audit.md), and every check
there has a negative control showing it can fail. To recheck from this
repo alone:

```bash
# Every agent commit names its role and session (the stamp hook lives in .git, out of agents' reach)
git log --all --format='%h %<(10,trunc)%(trailers:key=Agent-Role,valueonly,separator=) %<(9,trunc)%(trailers:key=Agent-Session,valueonly,separator=) %s' | grep -v '^[0-9a-f]* *  '

# The extract clone's history never held the eval data
git clone -q evidence/clones/extract.bundle /tmp/ex && \
  git -C /tmp/ex cat-file -e $(git rev-parse main:evals/notices.jsonl) 2>/dev/null \
  && echo HELD || echo "never held notices.jsonl"

# The tool-call logs are unedited (any change breaks the chain)
python3 -c "import sys,glob; sys.path.insert(0,'.claude/hooks'); import chainlog; \
  [print(f, chainlog.verify(f)) for f in sorted(glob.glob('evidence/logs/*.log'))]"

# Order: extract ended before evals-data started, and never ran again
cat evidence/sessions.log
```

The bundles contain each clone's reachable history; the audit also
checked the objects that aren't reachable from any branch. The
tests bundle will show three code blobs: that is incident 4, explained
below.

## What happened, in order

| Phase | What ran | Result |
|---|---|---|
| Setup | contract, packs, roles, guard, gate, stamps, audit; one real-session guard test | 17 probes, blocked or allowed as designed |
| Build | extract, api and tests in parallel; evals-data call after extract; worker at "db ready" | 143/143 tests passed on the first integration; evals 1.00 |
| Review | fresh reviewer in a read-only clone | 5 findings; 2 fixed by the owning agents, 3 deferred with reasons |
| Demo | api agent removed the raw-bytes signature check in a `DEMO:` commit | 7 tests failed, including the brief's signed example; the agent's revert restored 156/156 |

### Agent scorecard

From [evidence/audit.md](evidence/audit.md). "Denied" counts guard
refusals; most were agents chaining `cat .claude/role` or `git -C`.

| Role | Model | Pack words | Tool calls | Denied | Gate attempts | Cost USD | Minutes |
|---|---|---|---|---|---|---|---|
| extract | Haiku | 596 | 13 | 3 | 1 | 0.01 | 0.4 |
| api | Opus | 1000 | 28 | 3 | 5 | 1.92 | 2.3 |
| worker | Opus | 1019 | 50 | 5 | 5 | 1.49 | 3.2 |
| tests | Opus | 2890 | 23 | 2 | 2 | 2.11 | 4.6 |
| evals-data | Opus, no tools | 653 | 0 | 0 | 0 | 0.11 | 0.5 |
| reviewer | Opus | 2434 | 14 | 0 | 0 | 0.38 | 1.2 |

**Total agent spend: $6.02.** That covers the agent sessions only. It
excludes the orchestrating session and the Phase 1 guard probes. Gate
attempts include follow-up sessions (contract amendment, review fix,
demo).

### Incidents (full detail in [evidence/incidents.md](evidence/incidents.md))

1. **A gap in the lean context, caught by an agent.** The api pack said
   "seed the fixtures from the brief" but did not contain the brief. The
   agent stopped at "db ready" instead of inventing tenants. I amended
   contract section 2 and pushed it through `amend` and `resume`. That
   was the requirement-change path, used for real.
2. **My stop gate blamed the worker for files it didn't write.** `sync`
   merged other agents' code into its clone. The worker refused to delete
   files or edit `.claude/`, and explained the cause. I fixed `sync` and
   re-ran its gate myself; that run is logged with an empty session id.
3. **My evals-call script failed to save its output.** I recovered with
   `REUSE=1`, so the record stays at one call.
4. **Code blobs reached the tests clone's history** through a
   contaminated `contract` branch.
   - The files were never on disk, and the agent cannot run code.
   - Its only actions afterwards were reading its pack and committing.
   - The fingerprint check reports ❌, and I left it that way.

## What breaks first in production

1. **SQLite write contention.** There is one writer at a time, with a 5 s
   busy timeout. Intake runs blocking SQLite calls inside an async
   handler (review finding 5), so one held lock stalls every request in
   the process. Before the review fix, a lock error even silently erased
   correct extractions (finding 3, now fixed). Move to Postgres, and
   take the database off the event loop.
2. **Stuck `processing` rows.** A crashed worker, or now a database error,
   leaves notices claimed forever. Nothing reclaims them (out of scope by
   the brief). Add a lease timestamp and a reaper.
3. **Poison messages and retry storms.** A validly signed body with a
   lone surrogate, or deeply nested JSON, returns 500 (findings 1 and 4).
   The vendor retries forever.
4. **The signature scheme.**
   - There is one shared secret per tenant, stored in plain text in the
     same database.
   - There is no timestamp or nonce, so a captured request can be
     replayed forever.
   - There is no key rotation.
5. **Extraction on real notices.** The regex extractor and the eval
   labels follow the same section 9 rules, so 1.00 measures conformance
   to the contract, not accuracy on real court notices. Real notices
   need a model behind the same `check()`, and an eval set built from
   real data.

## Known gaps

- **The guard is not a sandbox.** It blocks by command string. Roles that
  run Python (api, worker, extract) could still read a sibling folder at
  runtime. The required separations do not depend on it. In production,
  run each agent in a sandboxed or cloud session with no network.
- **No OS-level network block.** Agents have no network tools and no
  credentials, but Python can open sockets.
- **The verification bundles cover reachable history only.** The full
  object-store check ran locally; its output is in `evidence/audit.md`.
- **Extract is frozen once the eval data exists.** If a reviewer finding
  were in `extractor/`, it would be a documented won't-fix rather than a
  relaunch. None was.
- **The deprecation warning is from the dependencies.** Starlette's
  `TestClient` warns about `httpx`; it is not from this code.

## Troubleshooting

```bash
tail -5 ../litigence-agents/<role>/.claude/gate.log      # why an agent could not stop
grep '"deny"' ../litigence-agents/<role>/.claude/guard.log  # what the guard refused
cat ../litigence-agents/sessions.log                      # who ran when
```

**`refusing: notices.jsonl is on disk`** — `agents.sh run extract`
found eval data somewhere under the agents folder or the repo. This is
deliberate: extract never runs while the answer sheet exists.

**`refusing: the contract branch contains code paths`** — someone merged
`main` into `contract`. Rebuild `contract` from docs-only commits
([incident 4](evidence/incidents.md)).

**`Stop gate: your commits touch files outside your slice`** right
after a `sync` or `amend` — the merged commits were not recorded in
`.claude/contract-tips`. Current `agents.sh` records them; for an older
clone, append the merged commit to that file.

**`path_guard: denied (command substitution or heredoc...)`** — the
agent tried `git commit -m "$(cat <<EOF ...)"`. Agents commit with one
plain `-m` line (`CLAUDE.md` rule 10).

## Architecture history

1. **Worktrees → separate clones.** A shared object store let `git show`
   read other branches.
2. **Prompt rules → guard hook.** "Don't read X" is not evidence; a
   logged denial is.
3. **Guard alone → blind roles cannot run code.** A real session showed
   Python bypassing the guard with a runtime path.
4. **Interactive agents → headless sessions with ids.** One id ties
   transcript, logs, commits and timeline.
5. **Full contract per agent → generated context packs.** Each agent
   reads one file of 600 to 1,000 words, instead of about 2,700.
6. **Trust "done" → Stop gate.** An agent can't finish with stray edits
   or broken imports.
7. **Plain logs → hash-chained logs, plus an audit with negative
   controls.** The evidence can be checked, and the checks themselves
   are shown to fail when they should.
