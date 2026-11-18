#!/usr/bin/env bash
# Architect-only helper. Each agent gets its own clone (own object store, no remote),
# a sparse checkout from .claude/roles.json, its own branch feat/<role>, and a role file.
#   scripts/agents.sh setup [role...]   create clones (default: api worker extract evals-data tests)
#   scripts/agents.sh launch <role>     print the claude command for that role
#   scripts/agents.sh sync <role>       merge main into that clone (worker only; never extract, evals-data, tests)
#   scripts/agents.sh collect           fetch every feat/<role> into this repo, copy guard logs to evidence/
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
AGENTS=${AGENTS_DIR:-$(dirname "$REPO")/litigence-agents}
BASE=${BASE:-main}
ALL=(api worker extract evals-data tests)

patterns() {
  python3 -c "import json,sys; c=json.load(open(sys.argv[1])); print('\n'.join(c['common_checkout']+c['roles'][sys.argv[2]]['checkout']))" \
    "$REPO/.claude/roles.json" "$1"
}

setup_role() {
  local role=$1 dir=$AGENTS/$1
  if [ -e "$dir" ]; then echo "skip $role: $dir exists"; return; fi
  mkdir -p "$AGENTS"
  git clone --quiet --no-hardlinks --no-checkout --branch "$BASE" "$REPO" "$dir"
  git -C "$dir" remote remove origin
  git -C "$dir" sparse-checkout init --no-cone
  patterns "$role" | git -C "$dir" sparse-checkout set --no-cone --stdin
  git -C "$dir" checkout --quiet -b "feat/$role"
  echo "$role" > "$dir/.claude/role"
  echo "ready $role -> $dir ($(cd "$dir" && git ls-files | wc -l | tr -d ' ') files on disk)"
}

launch() {
  local role=$1 tools="Bash,Read,Edit,Write,Glob,Grep" extra="--disable-slash-commands"
  if [ "$role" = worker ]; then tools="$tools,Skill"; extra=""; fi
  local prompt="You are the $role agent. Read CLAUDE.md, docs/contract.md, tasks/$role.md and plans/$role.md. Execute plans/$role.md step by step, commit after each step, and report at each CHECKPOINT."
  echo "cd '$AGENTS/$role' && PATH='$AGENTS/.venv/bin':\$PATH AGENT_ROLE=$role claude --setting-sources project --settings .claude/agent-settings.json --strict-mcp-config --mcp-config '{\"mcpServers\":{}}' --tools $tools $extra \"$prompt\""
}

case "${1:-}" in
  setup) shift
    if [ ! -x "$AGENTS/.venv/bin/python" ]; then
      mkdir -p "$AGENTS" && python3 -m venv "$AGENTS/.venv" && "$AGENTS/.venv/bin/pip" install --quiet -r "$REPO/requirements.txt"
    fi
    for r in "${@:-${ALL[@]}}"; do setup_role "$r"; done ;;
  launch) launch "$2" ;;
  sync)
    case "$2" in extract|evals-data|tests) echo "refusing: $2 must never receive main"; exit 1 ;; esac
    git -C "$AGENTS/$2" pull --no-rebase --no-edit --quiet "$REPO" main && echo "synced $2" ;;
  collect)
    mkdir -p "$REPO/evidence"
    for r in "${ALL[@]}"; do
      [ -d "$AGENTS/$r" ] || continue
      git -C "$REPO" fetch --quiet "$AGENTS/$r" "feat/$r:feat/$r"
      cp "$AGENTS/$r/.claude/guard.log" "$REPO/evidence/guard-$r.log" 2>/dev/null || : > "$REPO/evidence/guard-$r.log"
      (cd "$AGENTS/$r" && git ls-files) > "$REPO/evidence/files-$r.txt"
      echo "== $r: changed files vs $BASE"; git -C "$REPO" diff --name-only "$BASE...feat/$r"
      echo "   denials: $(grep -c '"deny"' "$REPO/evidence/guard-$r.log" || true)"
    done ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
