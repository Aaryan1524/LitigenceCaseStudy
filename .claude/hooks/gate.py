#!/usr/bin/env python3
"""Stop gate: an agent cannot finish until its slice is clean.

Structural checks only (agents write all behavioural tests):
  1. no uncommitted or untracked work
  2. at least one commit by this role, and every file its commits touched is inside its write allowlist
  3. its modules import (tests: every file parses with ast, nothing executes)
Exit 2 sends the problems back to the agent. After 3 failed attempts it lets the agent stop and logs "gave_up".
No .claude/role file (architect or reviewer checkout): does nothing.
"""
import ast
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chainlog  # noqa: E402

MAX_ATTEMPTS = 3


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def main():
    role_file = ROOT / ".claude" / "role"
    if not role_file.exists():
        sys.exit(0)
    role = role_file.read_text().strip()
    spec = json.loads((ROOT / ".claude" / "roles.json").read_text())["roles"][role]
    counter = ROOT / ".claude" / "gate.count"
    attempt = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(attempt))

    problems = []
    dirty = git("status", "--porcelain").strip()
    if dirty:
        problems.append("uncommitted or untracked files; commit them or delete them:\n" + dirty)

    if not spec["write"]:  # read-only role (reviewer): only a clean tree is required
        if problems:
            print("Stop gate: you are read-only; remove or revert:\n" + dirty, file=sys.stderr)
            sys.exit(0 if attempt >= MAX_ATTEMPTS else 2)
        sys.exit(0)
    base = (ROOT / ".claude" / "base").read_text().strip()
    tips_file = ROOT / ".claude" / "contract-tips"  # contract commits merged in by the architect are not the agent's work
    tips = ["^" + t for t in tips_file.read_text().split()] if tips_file.exists() else []
    touched = {f for f in git("log", "--no-merges", "--format=", "--name-only", f"{base}..HEAD", *tips).splitlines() if f}
    if not touched:
        problems.append("no commits from you yet; finish your plan and commit")
    outside = sorted(f for f in touched if not any(fnmatch.fnmatch(f, p) for p in spec["write"]))
    if outside:
        problems.append("your commits touch files outside your slice " + str(spec["write"]) + ": " + ", ".join(outside))

    check = spec.get("gate")
    if check == "ast":
        for f in sorted((ROOT / "tests").rglob("*.py")) if (ROOT / "tests").exists() else []:
            try:
                ast.parse(f.read_text(), filename=str(f))
            except SyntaxError as e:
                problems.append(f"{f.relative_to(ROOT)} does not parse: line {e.lineno}: {e.msg}")
    elif check:
        r = subprocess.run(check, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-6:])
            problems.append(f"import check failed ({check}):\n{tail}")

    if not problems:
        chainlog.append(ROOT / ".claude" / "gate.log", {"role": role, "attempt": attempt, "result": "pass",
                                                        "files": sorted(touched), "session": os.environ.get("AGENT_SESSION", "")})
        sys.exit(0)
    gave_up = attempt >= MAX_ATTEMPTS
    chainlog.append(ROOT / ".claude" / "gate.log", {"role": role, "attempt": attempt, "result": "gave_up" if gave_up else "fail",
                                                    "problems": problems, "session": os.environ.get("AGENT_SESSION", "")})
    if gave_up:
        sys.exit(0)
    print("Stop gate: you are not done yet.\n- " + "\n- ".join(problems), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
