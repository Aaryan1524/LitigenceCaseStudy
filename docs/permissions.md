# Agent permissions and isolation

Every agent runs as its own `claude` process in its own clone of this repo, started by `scripts/agents.sh run <role>`. The one exception is evals-data, which is a single LLM call with no tools. Agents never talk to each other; the architect is the only channel.

## Launch (what `agents.sh run` passes, and why)
| Setting | Why |
|---|---|
| Working directory `litigence-agents/<role>` | Its own clone: own object store, no remote, sparse checkout containing only its role's files (`.claude/roles.json` → `checkout`) |
| `--agent <role>` (`.claude/agents/<role>.md`) | Role as a versioned file: model, tool list, short system prompt. Verified in the init event: extract ran on Haiku with only its listed tools |
| `--setting-sources project` | Skips the user's own settings, hooks and plugins |
| `--settings .claude/agent-settings.json` | The allow and deny rules below |
| `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | No MCP servers, so the user's connectors are never visible. Verified: `mcp_servers: []` |
| `--disable-slash-commands` (all but worker) | No user skills or commands. The worker keeps `Skill` for its `worker-pipeline` skill |
| `-p --permission-prompts none` | Headless: anything not allowed is denied automatically, so nobody approves things by accident |
| `--max-budget-usd` (extract 3, api/worker/tests 15) | A hard cost ceiling per agent |
| `--session-id <uuid>`, `AGENT_SESSION`, `AGENT_ROLE` | One id ties together the transcript, the guard and gate logs, the commit stamps and `sessions.log` |
| `PATH=<agents>/.venv/bin:$PATH` | A shared venv with only the four allowed dependencies |

## agent-settings.json
- **Default mode:** `acceptEdits`. The path guard still decides which files may be touched.
- **Allow:** `python`, `pytest`, `sqlite3`, local git (status, add, commit, diff, log), `ls`, `pwd`, `wc`, `cd`, `head`, `tail`, `cat`, `echo`, the worker skill scripts.
- **Deny:** web fetch and search, `Agent` (no subagents), `curl`, `wget`, `ssh`, `scp`, `gh`, `git push/fetch/pull/remote/clone`, `pip` (also `python -m pip`), `rm -rf`, edits to `.claude/**`, `docs/**`, `CLAUDE.md`.

## Path guard (`.claude/hooks/path_guard.py`, PreToolUse on every tool)
- **File tools:** each path is resolved to its real location and must match the role's read or write allowlist. Anything outside the clone is denied.
- **Bash, per role:**
  - Command prefixes come from an allowlist. evals-data and tests have no `python` or `pytest`, so they cannot run code.
  - These are denied: `..`, absolute paths outside the clone, `~`, shell variables, `$(...)`, backticks, heredocs, redirects into protected paths, git global options, and git subcommands that reach other refs.
- **Logging:** every call goes to `.claude/guard.log` as a hash-chained line (`.claude/hooks/chainlog.py`), whether allowed or denied, so a missing or edited line is detectable.

## Stop gate (`.claude/hooks/gate.py`, on Stop)
An agent cannot finish until:
1. its tree is clean;
2. it has made at least one commit, and every file its own commits touched is inside its write allowlist. Contract and synced commits merged in by the architect are excluded through `.claude/contract-tips`;
3. its modules import. For tests, every file must parse with `ast`; nothing executes.

The gate gives up after 3 failed attempts and logs `gave_up`. The checks are structural only, because agents write all behavioural tests.

## Commit stamps
`setup` installs a `prepare-commit-msg` hook in each clone's `.git/hooks`. Agents cannot reach `.git`, and `--no-verify` does not skip this hook. Every agent commit gets `Agent-Role` and `Agent-Session` trailers. Merges the architect runs get `Agent-Role: architect`.

## How each separation holds, and how it is proven
| Separation | Mechanism | Proof (`scripts/agents.sh audit` → `evidence/audit.md`) |
|---|---|---|
| extract vs `evals/notices.jsonl` | evals-data is one LLM call with no tools, in an empty temp directory. Ordering is enforced: extract refuses to start if any `notices.jsonl` exists, evals-data refuses until extract has ended, and extract is frozen afterwards | Fingerprints: no `evals/` blob in extract's object store, and no `extractor/` blob in evals-data's. `sessions.log` timeline. The call record shows `num_turns: 1` and no tool use |
| tests vs code | The tests agent cannot run code. Its clone never receives `main`. Its only feedback is test ids and one-line messages (`agents.sh report tests`, `--tb=no`) | Fingerprints: no `app/`, `worker/` or `extractor/` blob in its object store. Read-before-write check on its guard log. A clean-tree check for conftest side effects |
| intake vs extractor | The api clone has no `extractor/` or `worker/`. The import-boundary test | `tests/test_boundaries.py` |
| reviewer vs authors | A fresh session in a fresh read-only clone (write allowlist empty) | `sessions.log`, its guard log |

Every audit check has a negative control showing it can fail. A fingerprint check against the architect repo reports `notices.jsonl` present, and a log with one byte changed reports its chain broken.

## Known limits
- **The guard reads command strings; it is not a sandbox.** A role that can run Python (api, worker, extract) could build a path at runtime and read another folder on the same disk. The two required separations don't rely on the guard against those roles: the blind roles execute nothing, and `notices.jsonl` never exists on disk while extract runs.
- **Network is not blocked at the OS level** for roles that run Python. They have no network tools, no credentials and nothing beyond the brief's fixtures.
- **Production upgrade:** run each agent as a cloud or sandboxed session with no network and a checkout of only its slice. This was not used here because cloud sessions need the repo pushed, and a cloud checkout has neither the role file nor the sparse slice.
