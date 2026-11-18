#!/usr/bin/env bash
# Architect-only helper. Each agent gets its own clone (own object store, no remote),
# a sparse checkout from .claude/roles.json, its own branch feat/<role>, and a role file.
#   scripts/agents.sh setup [role...]   create clones (default: api worker extract evals-data tests)
#   scripts/agents.sh run <role>        check ordering rules, then run that agent's claude session here
#   scripts/agents.sh amend <role>      merge the contract branch into a clone (any role)
#   scripts/agents.sh sync <role>       merge main into a clone (worker only)
#   scripts/agents.sh check <role>      architect-side acceptance for roles that cannot run code
#   scripts/agents.sh report tests      pytest on main, ids and messages only (the only output the tests agent gets)
#   scripts/agents.sh collect [role...] fetch feat/<role> into this repo, copy evidence
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
AGENTS=${AGENTS_DIR:-$(dirname "$REPO")/litigence-agents}
BASE=${BASE:-main}
ALL=(api worker extract evals-data tests)
PY="$AGENTS/.venv/bin/python"
LOCKS="$AGENTS/.locks"
SESS="$AGENTS/sessions.log"
MCP='{"mcpServers":{}}'

refuse() { echo "refusing: $*"; exit 1; }
alive() { [ -f "$LOCKS/$1.pid" ] && kill -0 "$(cat "$LOCKS/$1.pid")" 2>/dev/null; }
logsess() { echo "$(date '+%Y-%m-%dT%H:%M:%S') $1 $2" >> "$SESS"; }

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

setup_role() {
  local role=$1 dir=$AGENTS/$1
  if [ -e "$dir" ]; then echo "skip $role: $dir exists"; return; fi
  git clone --quiet --no-hardlinks --no-checkout --branch "$BASE" "$REPO" "$dir"
  git -C "$dir" remote remove origin
  git -C "$dir" sparse-checkout init --no-cone
  patterns "$role" | git -C "$dir" sparse-checkout set --no-cone --stdin
  git -C "$dir" checkout --quiet -b "feat/$role"
  echo "$role" > "$dir/.claude/role"
  echo "ready $role -> $dir ($(cd "$dir" && find . -path ./.git -prune -o -type f -print | wc -l | tr -d ' ') files on disk)"
}

run() {
  local role=$1 bin=${CLAUDE_BIN:-claude}
  if [ "$role" = reviewer ]; then
    [ "$(git -C "$REPO" branch --show-current)" = main ] || refuse "switch the architect checkout to main first"
    cd "$REPO" && exec "$bin" --permission-mode plan --strict-mcp-config --mcp-config "$MCP" \
      "You are the reviewer agent. Read CLAUDE.md, docs/contract.md, tasks/reviewer.md and plans/reviewer.md, then execute the plan. Do not change any file."
  fi
  [ -d "$AGENTS/$role" ] || refuse "no clone for $role; run setup first"
  ordering "$role"
  mkdir -p "$LOCKS"
  echo $$ > "$LOCKS/$role.pid"
  logsess start "$role"
  trap 'logsess end '"$role"'; rm -f "$LOCKS/'"$role"'.pid"' EXIT
  local tools="Bash,Read,Edit,Write,Glob,Grep" extra="--disable-slash-commands"
  if [ "$role" = worker ]; then tools="$tools,Skill"; extra=""; fi
  (cd "$AGENTS/$role" && PATH="$AGENTS/.venv/bin:$PATH" AGENT_ROLE="$role" "$bin" \
    --setting-sources project --settings .claude/agent-settings.json --strict-mcp-config --mcp-config "$MCP" \
    --tools "$tools" $extra \
    "You are the $role agent. Read CLAUDE.md, docs/contract.md, tasks/$role.md and plans/$role.md. Execute plans/$role.md step by step, commit after each step, and report at each CHECKPOINT.") || true
}

check() {
  local dir=$AGENTS/$1
  case "$1" in
    evals-data)
      "$PY" - "$dir/evals/notices.jsonl" <<'PYEOF'
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
      ;;
    tests) (cd "$dir" && "$PY" -m pytest --collect-only -q -p no:cacheprovider 2>&1 | grep -vE '^\s+(File|  )' | tail -25) ;;
    *) refuse "$1 runs its own acceptance check" ;;
  esac
}

case "${1:-}" in
  setup) shift
    mkdir -p "$AGENTS"
    if [ ! -x "$PY" ]; then python3 -m venv "$AGENTS/.venv" && "$AGENTS/.venv/bin/pip" install --quiet -r "$REPO/requirements.txt"; fi
    for r in "${@:-${ALL[@]}}"; do setup_role "$r"; done ;;
  run) run "$2" ;;
  amend) git -C "$AGENTS/$2" pull --no-rebase --no-edit --quiet "$REPO" contract && echo "amended $2 from contract" ;;
  sync)
    [ "$2" = worker ] || refuse "only worker receives main"
    git -C "$AGENTS/$2" pull --no-rebase --no-edit --quiet "$REPO" main && echo "synced $2" ;;
  check) check "$2" ;;
  report)
    [ "${2:-}" = tests ] || refuse "usage: report tests"
    (cd "$REPO" && "$PY" -m pytest --tb=no -rfE -q -p no:cacheprovider 2>&1 | tail -40) ;;
  collect) shift
    mkdir -p "$REPO/evidence"
    cp "$SESS" "$REPO/evidence/sessions.log" 2>/dev/null || true
    for r in "${@:-${ALL[@]}}"; do
      [ -d "$AGENTS/$r" ] || continue
      if [ "$r" = evals-data ] && alive extract; then echo "skip evals-data: extract still running"; continue; fi
      git -C "$REPO" fetch --quiet "$AGENTS/$r" "feat/$r:feat/$r"
      cp "$AGENTS/$r/.claude/guard.log" "$REPO/evidence/guard-$r.log" 2>/dev/null || : > "$REPO/evidence/guard-$r.log"
      (cd "$AGENTS/$r" && find . -path ./.git -prune -o -type f -print | sort) > "$REPO/evidence/files-$r.txt"
      echo "== $r: changed files vs $BASE"; git -C "$REPO" diff --name-only "$BASE...feat/$r"
      echo "   calls: $(wc -l < "$REPO/evidence/guard-$r.log" | tr -d ' ')  denials: $(grep -c '"deny"' "$REPO/evidence/guard-$r.log" || true)"
    done ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
