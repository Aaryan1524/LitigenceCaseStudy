# Incidents (all found during the build, all architect-side unless stated)

## 1. Seed fixtures missing from the api context pack (contract gap, caught by an agent)
The contract said "seed the two tenants and four matters from the brief", but the lean api pack does not include the brief. The api agent stopped at "db ready" and reported the gap instead of inventing fixtures. Fix: contract section 2 now lists the fixtures explicitly, the packs were regenerated, and the change went to the agent through the `contract` branch (`amend`, then `resume`). See the change log in `docs/contract.md`.

## 2. Stop gate false positive on the worker (architect bug)
`sync worker` merged main into the worker clone, and the gate counted api and extract files as the worker's. The worker refused to tamper: it did not delete files, rewrite history or edit `.claude/`. It explained the cause, and the gate gave up after 3 attempts as designed. Fix: `sync` now records merged commits in `.claude/contract-tips`. The architect re-ran the gate once by hand, and it passed. That run is logged with an empty session id, because the architect ran it, not the agent.

## 3. evals-call save bug (architect bug)
The no-tools call succeeded, but the script did not create `evals/` before saving. Fix: `mkdir -p`, plus `REUSE=1`, which saves the recorded output without a second call. Provenance stays one call (`num_turns: 1`, session `6d6d9a24`).

## 4. Code reached the tests clone's git history (architect error; separation held in practice, but the proof is broken)
- **What happened:** at 18:13:27 the architect fast-forwarded `contract` to `main`, which by then contained integrated code. That broke the rule that `contract` never carries code. At 18:15:06 the review-round `amend tests` merged that branch into the tests clone. Its object store then held 3 of the 7 current `app/`, `worker/` and `extractor/` blobs. The audit's fingerprint check reports this as ❌.
- **Why the separation still held in practice:**
  - The files were never on disk; the sparse checkout excludes them.
  - The tests agent cannot run code.
  - The guard denies every git command that reads objects (`show`, `cat-file`, `log -p` to other refs, `checkout`, `restore`, global options).
  - In the only session after the merge (18:15:26 to 18:16:28), the tests agent made three calls: a denied `grep` of its own pack, a `Read` of `context/tests.md`, and `git add tests/ && git commit`. All its tests had been written in the first session (18:04 to 18:08), when the contract was clean.
- **Fix:**
  - `contract` was rebuilt from its last clean commit (`d8cee56`) plus the docs-only commits. The bad branch is kept as `contract-contaminated` for inspection.
  - `agents.sh amend` now refuses if `contract` has ever carried a code path.
  - `audit` checks the same thing.
