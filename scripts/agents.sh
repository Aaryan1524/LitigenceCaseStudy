#!/usr/bin/env bash
# Architect-only orchestrator. Each agent gets its own clone (own object store, no remote), a sparse
# checkout from .claude/roles.json, branch feat/<role>, a role file, a base commit and a commit-stamping hook.
#   scripts/agents.sh setup [role...]          create clones (default: api worker extract evals-data tests)
#   scripts/agents.sh run <role>               ordering checks, then the agent's session (HEADLESS=1 for -p, logged)
#   scripts/agents.sh resume <role> "<msg>"    send a follow-up to a headless agent's session
#   scripts/agents.sh evals-call               evals-data as one no-tools LLM call; saves, validates, commits
#   scripts/agents.sh amend <role>             merge the contract branch into a clone
#   scripts/agents.sh sync worker              merge main into the worker clone
#   scripts/agents.sh report tests             pytest on main, ids and messages only
#   scripts/agents.sh collect [role...]        fetch feat/<role> into this repo, copy evidence
#   scripts/agents.sh audit                    write evidence/audit.md (provenance, separation proofs, scorecard)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
AGENTS=${AGENTS_DIR:-$(dirname "$REPO")/litigence-agents}
BASE=${BASE:-main}
ALL=(api worker extract evals-data tests)   # reviewer: setup reviewer after integration (BASE=main)
PY="$AGENTS/.venv/bin/python"
LOCKS="$AGENTS/.locks"
SESS="$AGENTS/sessions.log"
LOGS="$AGENTS/logs"
MCP='{"mcpServers":{}}'
CLAUDE_BIN=${CLAUDE_BIN:-claude}

refuse() { echo "refusing: $*"; exit 1; }
alive() { [ -f "$LOCKS/$1.pid" ] && kill -0 "$(cat "$LOCKS/$1.pid")" 2>/dev/null; }
logsess() { echo "$(date '+%Y-%m-%dT%H:%M:%S') $1 $2 ${3:-}" >> "$SESS"; }
budget() { case "$1" in extract) echo 3 ;; tests|api|worker) echo 15 ;; *) echo 10 ;; esac; }

patterns() {
  python3 -c "import json,sys; c=json.load(open(sys.argv[1])); print('\n'.join(c['common_checkout']+c['roles'][sys.argv[2]]['checkout']))" \
    "$REPO/.claude/roles.json" "$1"
}

# extract and evals-data never overlap, and notices.jsonl never exists on disk while extract runs.
# Once evals-data has started, extract is frozen for the rest of the exercise.
ordering() {
  local role=$1
  alive "$role" && refuse "$role is already running"
  case "$role" in
    extract)
      grep -q " start evals-data" "$SESS" 2>/dev/null && refuse "extract is frozen: evals-data has started"
      local found
      found=$(find "$AGENTS" "$REPO" -path '*/.git' -prune -o -path '*/.venv' -prune -o -name notices.jsonl -print 2>/dev/null | head -1)
      [ -n "$found" ] && refuse "notices.jsonl is on disk: $found"
      git -C "$REPO" rev-parse -q --verify refs/heads/feat/evals-data >/dev/null && refuse "feat/evals-data exists in the repo"
      ;;
    evals-data)
      alive extract && refuse "extract is still running"
      grep -q " end extract" "$SESS" 2>/dev/null || refuse "extract has not finished yet"
      ;;
  esac
  return 0
}

install_stamp_hook() {
  cat > "$1/.git/hooks/prepare-commit-msg" <<'HOOK'
#!/bin/sh
# Stamps every commit. Agent sessions carry AGENT_SESSION; anything else (architect merges) is stamped architect.
grep -q '^Agent-Role:' "$1" && exit 0
if [ -n "$AGENT_SESSION" ]; then
  git interpret-trailers --in-place --trailer "Agent-Role: $(cat .claude/role)" --trailer "Agent-Session: $AGENT_SESSION" "$1"
else
  git interpret-trailers --in-place --trailer "Agent-Role: architect" "$1"
fi
HOOK
  chmod +x "$1/.git/hooks/prepare-commit-msg"
}

setup_role() {
  local role=$1 dir=$AGENTS/$1
  if [ -e "$dir" ]; then echo "skip $role: $dir exists"; return; fi
  git clone --quiet --no-hardlinks --no-checkout --branch "$BASE" "$REPO" "$dir"
  git -C "$dir" remote remove origin
  git -C "$dir" sparse-checkout init --no-cone
  patterns "$role" | git -C "$dir" sparse-checkout set --no-cone --stdin
  git -C "$dir" checkout --quiet -b "feat/$role"
  echo "$role" > "$dir/.claude/role"
  git -C "$dir" rev-parse HEAD > "$dir/.claude/base"
  install_stamp_hook "$dir"
  echo "ready $role -> $dir ($(cd "$dir" && find . -path ./.git -prune -o -type f -print | wc -l | tr -d ' ') files on disk)"
}

agent_flags() {
  local role=$1
  FLAGS=(--agent "$role" --setting-sources project --settings .claude/agent-settings.json
         --strict-mcp-config --mcp-config "$MCP")
  [ "$role" = worker ] || FLAGS+=(--disable-slash-commands)
  [ "$role" = reviewer ] && FLAGS+=(--tools "Bash,Read,Glob,Grep")
  if [ -n "${HEADLESS:-}" ]; then
    FLAGS+=(-p --output-format stream-json --verbose --permission-prompts none --max-budget-usd "$(budget "$role")")
  fi
}

run() {
  local role=$1
  [ "$role" = evals-data ] && refuse "evals-data runs as a no-tools call: scripts/agents.sh evals-call"
  [ -d "$AGENTS/$role" ] || refuse "no clone for $role; run setup first"
  ordering "$role"
  mkdir -p "$LOCKS" "$LOGS"
  local sid; sid=$(uuidgen | tr 'A-Z' 'a-z')
  echo $$ > "$LOCKS/$role.pid"
  echo "$sid" > "$LOCKS/$role.session"
  logsess start "$role" "$sid"
  trap 'logsess end '"$role"' '"$sid"'; rm -f "$LOCKS/'"$role"'.pid"' EXIT
  agent_flags "$role"
  local out=/dev/stdout; [ -n "${HEADLESS:-}" ] && out="$LOGS/$role.jsonl"
  (cd "$AGENTS/$role" && PATH="$AGENTS/.venv/bin:$PATH" AGENT_ROLE="$role" AGENT_SESSION="$sid" \
    "$CLAUDE_BIN" "${FLAGS[@]}" --session-id "$sid" \
    "Start now: read context/$role.md and execute the plan to the end." >> "$out") || true
}

resume() {
  local role=$1 msg=$2
  [ -f "$LOCKS/$role.session" ] || refuse "no session recorded for $role"
  ordering "$role"
  local sid; sid=$(cat "$LOCKS/$role.session")
  echo $$ > "$LOCKS/$role.pid"
  logsess start "$role" "$sid"
  trap 'logsess end '"$role"' '"$sid"'; rm -f "$LOCKS/'"$role"'.pid"' EXIT
  rm -f "$AGENTS/$role/.claude/gate.count"
  HEADLESS=1 agent_flags "$role"
  (cd "$AGENTS/$role" && PATH="$AGENTS/.venv/bin:$PATH" AGENT_ROLE="$role" AGENT_SESSION="$sid" \
    "$CLAUDE_BIN" "${FLAGS[@]}" --resume "$sid" "$msg" >> "$LOGS/$role.jsonl") || true
}

evals_call() {
  local dir=$AGENTS/evals-data
  [ -d "$dir" ] || refuse "no clone for evals-data; run setup first"
  ordering evals-data
  mkdir -p "$LOCKS" "$LOGS"
  local sid; sid=$(uuidgen | tr 'A-Z' 'a-z')
  local empty; empty=$(mktemp -d)
  echo $$ > "$LOCKS/evals-data.pid"
  logsess start evals-data "$sid"
  trap 'logsess end evals-data '"$sid"'; rm -f "$LOCKS/evals-data.pid"' EXIT
  local prompt="$dir/context/evals-data.md"
  (cd "$empty" && "$CLAUDE_BIN" -p --tools "" --model opus --strict-mcp-config --mcp-config "$MCP" \
     --setting-sources "" --disable-slash-commands --session-id "$sid" --output-format json < "$prompt" > "$LOGS/evals-data.json")
  "$PY" - "$LOGS/evals-data.json" "$dir/evals/notices.jsonl" <<'PYEOF'
import json, sys
res = json.load(open(sys.argv[1]))["result"]
lines = [l.strip() for l in res.splitlines() if l.strip().startswith("{")]
open(sys.argv[2], "w").write("\n".join(lines) + "\n")
print(f"saved {len(lines)} lines")
PYEOF
  check_evals "$dir/evals/notices.jsonl"
  (cd "$dir" && git add evals/notices.jsonl && AGENT_SESSION="$sid" git commit -q -m "evals: 20 labelled notices from one no-tools call")
  "$PY" - "$LOGS/evals-data.json" "$prompt" "$sid" "$REPO/evidence/evals-call.json" <<'PYEOF'
import hashlib, json, sys
res = json.load(open(sys.argv[1]))
rec = {"session": sys.argv[3], "tools": "none", "cwd": "empty temp dir", "model_usage": res.get("modelUsage") or res.get("usage"),
       "prompt_sha256": hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest(),
       "output_sha256": hashlib.sha256(res["result"].encode()).hexdigest(),
       "cost_usd": res.get("total_cost_usd"), "duration_ms": res.get("duration_ms")}
json.dump(rec, open(sys.argv[4], "w"), indent=2); print("recorded", sys.argv[4])
PYEOF
}

check_evals() {
  "$PY" - "$1" <<'PYEOF'
import json, sys
tenants = {"alderbrook-law", "fernwick-llp"}
lines = open(sys.argv[1]).read().splitlines()
errors = []
for n, line in enumerate(lines, 1):
    try:
        o = json.loads(line)
        assert set(o) >= {"id", "tenant", "text", "expected"}, "missing keys"
        assert o["tenant"] in tenants, "unknown tenant"
        assert set(o["expected"]) == {"filing_type", "matter_id", "filed_date"}, "expected keys"
    except Exception as e:
        errors.append(f"line {n}: {e}")
print(f"{len(lines)} lines, {len(errors)} errors"); print("\n".join(errors))
sys.exit(1 if errors or len(lines) != 20 else 0)
PYEOF
}

case "${1:-}" in
  setup) shift
    mkdir -p "$AGENTS" "$REPO/evidence"
    if [ ! -x "$PY" ]; then python3 -m venv "$AGENTS/.venv" && "$AGENTS/.venv/bin/pip" install --quiet -r "$REPO/requirements.txt"; fi
    for r in "${@:-${ALL[@]}}"; do setup_role "$r"; done ;;
  run) run "$2" ;;
  resume) resume "$2" "$3" ;;
  evals-call) evals_call ;;
  amend)
    git -C "$AGENTS/$2" fetch --quiet "$REPO" contract
    git -C "$AGENTS/$2" rev-parse FETCH_HEAD >> "$AGENTS/$2/.claude/contract-tips"
    git -C "$AGENTS/$2" merge --quiet --no-edit FETCH_HEAD && echo "amended $2 from contract" ;;
  sync)
    [ "$2" = worker ] || refuse "only worker receives main"
    git -C "$AGENTS/$2" pull --no-rebase --no-edit --quiet "$REPO" main && echo "synced $2" ;;
  report)
    [ "${2:-}" = tests ] || refuse "usage: report tests"
    (cd "$REPO" && "$PY" -m pytest --tb=no -rfE -q -p no:cacheprovider 2>&1 | tail -40) ;;
  collect) shift
    mkdir -p "$REPO/evidence/logs"
    cp "$SESS" "$REPO/evidence/sessions.log" 2>/dev/null || true
    for r in "${@:-${ALL[@]}}"; do
      [ -d "$AGENTS/$r" ] || continue
      if [ "$r" = evals-data ] && alive extract; then echo "skip evals-data: extract still running"; continue; fi
      git -C "$REPO" fetch --quiet "$AGENTS/$r" "feat/$r:feat/$r"
      for f in guard.log gate.log; do cp "$AGENTS/$r/.claude/$f" "$REPO/evidence/logs/$r.$f" 2>/dev/null || true; done
      cp "$LOGS/$r.jsonl" "$REPO/evidence/logs/$r.transcript.jsonl" 2>/dev/null || true
      (cd "$AGENTS/$r" && find . -path ./.git -prune -o -type f -print | sort) > "$REPO/evidence/logs/$r.files-on-disk.txt"
      echo "== $r: $(git -C "$REPO" diff --name-only "$BASE...feat/$r" | wc -l | tr -d ' ') files changed vs $BASE"
    done ;;
  audit) AGENTS_DIR="$AGENTS" python3 "$REPO/scripts/audit.py" ;;
  *) sed -n '2,13p' "$0"; exit 1 ;;
esac
