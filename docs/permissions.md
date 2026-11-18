# Agent permissions and isolation

Every build agent runs as its own `claude` process in its own clone, launched by the command `scripts/agents.sh launch <role>` prints.

## Launch flags
| Flag | Why |
|---|---|
| `cd <agents>/<role>` | The agent's working directory is its own clone. It has its own object store, no remote, and a sparse checkout with only its role's files. |
| `AGENT_ROLE=<role>` | Cross-checked against `.claude/role`. A mismatch denies every call. |
| `--setting-sources project` | Skips the user's own settings, hooks and plugins. |
| `--settings .claude/agent-settings.json` | The agent allow and deny rules below. |
| `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | No MCP servers. The user's connectors (Drive, Docs, Vercel, Docker) are never visible. Verified: init shows `mcp_servers: []`. |
| `--tools Bash,Read,Edit,Write,Glob,Grep` | No web, no subagents, no notebooks. The worker also gets `Skill` for its worker-pipeline skill. |
| `--disable-slash-commands` | No user skills or commands (all roles except worker). |
| `PATH=<agents>/.venv/bin:$PATH` | A shared venv with only the four allowed dependencies. Agents cannot `pip install`. |

## agent-settings.json
- **Default mode:** `acceptEdits`. File edits inside the clone don't prompt. The path guard still decides which files may be touched.
- **Allow:** `python`, `pytest`, `sqlite3`, local git (status, add, commit, diff, log) and the worker skill scripts. These let agents work without prompting.
- **Deny:** web fetch and search, `Agent`, `curl`, `wget`, `ssh`, `scp`, `gh`, `git push`, `git fetch`, `git pull`, `git remote`, `git clone`, `pip install`, `rm -rf`, and edits to `.claude/**`, `docs/**` and `CLAUDE.md`. Nothing leaves the machine, and nothing changes the rules.

## Path guard (`.claude/hooks/path_guard.py`, PreToolUse on every tool)
- **File tools:** a path is resolved to its real location, then must match the role's read or write allowlist in `.claude/roles.json`. Anything outside the clone is denied.
- **Bash:**
  - The command must start with a prefix on the role's allowlist.
  - These are denied: `..`, absolute filesystem paths, `~`, shell variables, command substitution, heredocs, and git subcommands that reach other refs (`show`, `checkout`, `fetch`, `-C`, and others).
- **Logging:** every call goes to `.claude/guard.log`, allowed or denied. An empty log means the hook never ran; it doesn't mean "no attempts".
- **Architect checkout:** with no `.claude/role`, everything is allowed and still logged.

## How each separation holds
| Separation | Mechanism | Evidence |
|---|---|---|
| extract vs `evals/notices.jsonl` | evals-data cannot run code. extract and evals-data never run at the same time (`agents.sh` refuses), so `notices.jsonl` is never on disk while extract runs. Each clone starts from a commit containing neither file. | `evidence/files-*.txt`, guard logs, `git diff --name-only main...feat/<role>` |
| tests vs code | The tests agent cannot run code. Its clone never receives `main`. It reads only through guarded file tools. | same as above |
| intake vs extractor | The import-boundary test, and the api clone has no `extractor/` or `worker/` | `tests/test_boundaries.py` |

## Known limit
The guard reads command strings; it is not a sandbox. Any role that can run Python (api, worker, extract) can build a path at runtime and read other folders on this disk. The two required separations don't rely on the guard against those roles:
- Neither blind role (evals-data, tests) can execute anything.
- `notices.jsonl` doesn't exist anywhere on disk while extract runs.

## Reviewer
The reviewer runs in the architect checkout on `main` with `--permission-mode plan`, so it cannot edit files. It starts fresh and has not written any of the code.
