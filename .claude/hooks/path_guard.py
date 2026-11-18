#!/usr/bin/env python3
"""PreToolUse path guard.

Role comes from <root>/.claude/role (written by scripts/agents.sh, never committed).
No role file  -> architect checkout: allow and log.
Role file     -> enforce .claude/roles.json; fail closed on anything unknown.
Every call is appended to <root>/.claude/guard.log as one JSON line.
Exit 2 blocks the tool call; stderr is shown to the agent.
"""
import fnmatch
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".claude" / "guard.log"
FILE_TOOLS = {"Read": "read", "Edit": "write", "Write": "write", "MultiEdit": "write", "NotebookEdit": "write"}
SEARCH_TOOLS = {"Glob", "Grep"}
ALWAYS_ALLOWED = {"TodoWrite", "Skill"}
DENY_GIT = {"show", "cat-file", "checkout", "switch", "restore", "grep", "worktree", "sparse-checkout",
            "fetch", "pull", "push", "remote", "merge", "rebase", "reset", "branch", "reflog", "stash",
            "ls-tree", "ls-files", "rev-list", "archive", "clone", "config", "submodule", "update-index"}


sys.path.insert(0, str(Path(__file__).resolve().parent))
import chainlog  # noqa: E402


def log(entry):
    entry["session"] = os.environ.get("AGENT_SESSION", "")
    chainlog.append(LOG, entry)


def decide(decision, reason, entry):
    entry.update(decision=decision, reason=reason)
    log(entry)
    if decision == "deny":
        print(f"path_guard: denied ({reason})", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


def rel(path_str):
    """Resolve a path against ROOT; return a posix relative path, or None if outside ROOT."""
    p = Path(path_str)
    p = (p if p.is_absolute() else ROOT / p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return None


def matches(path, patterns):
    return any(path == pat or fnmatch.fnmatch(path, pat) for pat in patterns)


FS_ROOTS = r"(Users|private|tmp|var|etc|Volumes|opt|System|Library|Applications|home|root|usr|bin|sbin|proc|dev(?!/null))"


def check_bash(cmd, allowed):
    if re.search(r"(^|[\s'\"=(:,])\.\.(/|\s|$|['\"])", cmd):
        return "parent directory reference; stay inside your checkout and use relative paths"
    if re.search(r"(^|[\s'\"=(:,])~", cmd):
        return "home path; use paths relative to the checkout root"
    for m in re.finditer(r"(?:^|(?<=[\s'\"=(:,]))(/" + FS_ROOTS + r"(?:/[^\s'\"),;]*)?)", cmd):
        if rel(m.group(1)) is None:
            return "filesystem path outside your checkout; use paths relative to the checkout root"
    if re.search(r">>?\s*['\"]?(\./)?(\.claude|docs|context|tasks|plans|CLAUDE\.md)", cmd):
        return "redirecting output into a protected path"
    if re.search(r"\.git(/|\b)(?!ignore)", cmd) or ".claude/role" in cmd:
        return "touches .git or the role file"
    if "`" in cmd or "$(" in cmd or "<<" in cmd:
        return 'command substitution or heredoc; commit with one plain line: git commit -m "message"'
    if re.search(r"-m\s+(pip|ensurepip|venv)\b|\bpip3?\b|ensurepip", cmd):
        return "installing packages is not allowed; the venv already has the four allowed dependencies"
    if re.search(r"\$\{|\$[A-Za-z_]", cmd):
        return "shell variables are not allowed; write the literal relative path"
    try:
        lex = shlex.shlex(cmd.replace("2>&1", "").replace("\n", " ; "), posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return "unparseable command"
    segments, cur = [], []
    for tok in tokens:
        if tok and set(tok) <= set(";&|"):
            segments.append(cur)
            cur = []
        else:
            cur.append(tok)
    segments.append(cur)
    for words in segments:
        while words and re.match(r"^[A-Z_]+=", words[0]):
            words = words[1:]
        if not words:
            continue
        if words[0] == "git" and len(words) > 1:
            if words[1].startswith("-") or any(w.startswith(("--git-dir", "--work-tree")) for w in words):
                return "git global options (-C, --git-dir, --work-tree) are not allowed"
            if words[1] in DENY_GIT or any(w in ("--all", "--branches", "--remotes", "--glob") for w in words):
                return f"git {words[1]} is not allowed; only status, add, commit, diff (working tree), log --oneline"
            if words[1] == "diff" and any(not w.startswith("-") for w in words[2:]):
                return "git diff against another ref is not allowed; use plain git diff or git diff --stat"
        norm = " ".join(words)
        if not any(norm == a or norm.startswith(a + " ") or (a.endswith("/") and norm.startswith(a)) for a in allowed):
            return f"'{words[0]}' is not allowed for this role; allowed: {', '.join(sorted(set(allowed)))}"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        print("path_guard: unreadable hook input", file=sys.stderr)
        sys.exit(2)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    role_file = ROOT / ".claude" / "role"
    role = role_file.read_text().strip() if role_file.exists() else None
    entry = {"role": role or "architect", "tool": tool,
             "target": tin.get("file_path") or tin.get("notebook_path") or tin.get("path") or tin.get("pattern") or tin.get("command")}

    if role is None:
        decide("allow", "architect checkout", entry)

    env_role = os.environ.get("AGENT_ROLE")
    if env_role and env_role != role:
        decide("deny", f"AGENT_ROLE={env_role} does not match role file {role}", entry)
    try:
        cfg = json.loads((ROOT / ".claude" / "roles.json").read_text())
        spec = cfg["roles"][role]
    except (OSError, ValueError, KeyError):
        decide("deny", f"no config for role {role}", entry)

    reads = cfg["common_read"] + spec["read"]
    if tool in ALWAYS_ALLOWED:
        decide("allow", "harmless tool", entry)

    if tool in FILE_TOOLS:
        target = tin.get("file_path") or tin.get("notebook_path") or ""
        r = rel(target)
        if r is None:
            decide("deny", "outside checkout", entry)
        if FILE_TOOLS[tool] == "write":
            if matches(r, cfg["protected"]) or not matches(r, spec["write"]):
                decide("deny", f"{r} not writable for {role}", entry)
        elif not matches(r, reads + spec["write"]):
            decide("deny", f"{r} not readable for {role}", entry)
        decide("allow", r, entry)

    if tool in SEARCH_TOOLS:
        base = tin.get("path") or "."
        r = rel(base)
        pattern = tin.get("pattern", "")
        if r is None or ".." in pattern or (tool == "Glob" and pattern.startswith(("/", "~"))):
            decide("deny", "search outside checkout", entry)
        if r.startswith(".git") or (r != "." and not any(p.startswith(r) or fnmatch.fnmatch(r, p) for p in reads)):
            decide("deny", f"search base {r} not readable for {role}", entry)
        decide("allow", f"search {r}", entry)

    if tool == "Bash":
        reason = check_bash(tin.get("command", ""), cfg["common_bash"] + spec["bash"])
        decide("deny" if reason else "allow", reason or "bash allowlisted", entry)

    decide("deny", f"tool {tool} not allowed for agents", entry)


if __name__ == "__main__":
    main()
