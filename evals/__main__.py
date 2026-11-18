"""`python -m evals`: run run_extraction over evals/notices.jsonl and report per-field accuracy.

Exit codes: 0 all fields >= 0.90, 1 some field below, 2 data file missing or malformed.
"""
import json
import sys
from pathlib import Path

from app.db import connect, init_db
from worker.checks import run_extraction

FIELDS = ("filing_type", "matter_id", "filed_date")
THRESHOLD = 0.90
DATA = Path(__file__).resolve().parent / "notices.jsonl"


def load(path: Path) -> list[dict]:
    cases = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
            _ = (case["id"], case["tenant"], case["text"])
            _ = [case["expected"][f] for f in FIELDS]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{path.name}:{lineno}: bad eval line ({exc!r})") from exc
        cases.append(case)
    return cases


def main(path: Path = DATA) -> int:
    if not path.is_file():
        print(f"error: eval data not found: {path}", file=sys.stderr)
        return 2
    try:
        cases = load(path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not cases:
        print(f"error: no eval cases in {path}", file=sys.stderr)
        return 2

    conn = connect(":memory:")
    init_db(conn)
    correct = {f: 0 for f in FIELDS}
    for case in cases:
        result = run_extraction(case["text"], case["tenant"], conn)
        misses = [f for f in FIELDS if result[f] != case["expected"][f]]
        for f in FIELDS:
            if f not in misses:
                correct[f] += 1
        if misses:
            got = {f: result[f] for f in misses}
            want = {f: case["expected"][f] for f in misses}
            print(f"MISS {case['id']}: got {got} want {want}")

    n = len(cases)
    failed = False
    for f in FIELDS:
        acc = correct[f] / n
        flag = "ok" if acc >= THRESHOLD else "BELOW 0.90"
        failed |= acc < THRESHOLD
        print(f"{f:<12} {correct[f]}/{n} = {acc:.2f} {flag}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
