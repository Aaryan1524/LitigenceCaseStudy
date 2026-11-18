"""Append-only, hash-chained JSON-lines log.

Each line carries `prev`: the sha256 of the previous line's bytes ("genesis" for the first).
Editing or deleting any line breaks every `prev` after it; scripts/audit.py verifies the chain.
An exclusive flock covers read-last-line + append, so parallel hook runs cannot fork the chain.
"""
import fcntl
import hashlib
import json
import os
import time


def append(path, entry):
    entry = dict(entry)
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError:
        return
    with os.fdopen(fd, "r+b") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            last = b""
            for line in f:
                if line.strip():
                    last = line.rstrip(b"\n")
            entry["prev"] = hashlib.sha256(last).hexdigest() if last else "genesis"
            f.seek(0, os.SEEK_END)
            f.write((json.dumps(entry, sort_keys=True) + "\n").encode())
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def verify(path):
    """Return (ok, number_of_lines, first_bad_line_number_or_None)."""
    prev = None
    n = 0
    try:
        lines = open(path, "rb").read().splitlines()
    except OSError:
        return True, 0, None
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        n += 1
        want = "genesis" if prev is None else hashlib.sha256(prev).hexdigest()
        try:
            if json.loads(line).get("prev") != want:
                return False, n, i
        except ValueError:
            return False, n, i
        prev = line
    return True, n, None
