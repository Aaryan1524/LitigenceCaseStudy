"""Run the contract's 20 notices through the worker's exact validation path."""
import argparse
import json
from pathlib import Path
import sys

from app.db import connect, init_db
from worker.checks import run_extraction

FIELDS = ("filing_type", "matter_id", "filed_date")
THRESHOLD = 0.90
DATA = Path(__file__).with_name("notices.jsonl")


def load_cases(path):
    cases = []
    ids = set()
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        try:
            case = json.loads(line)
            if not isinstance(case, dict) or set(case) != {"id", "tenant", "text", "expected"}:
                raise ValueError("expected id, tenant, text, expected")
            if not isinstance(case["id"], str) or not case["id"] or case["id"] in ids:
                raise ValueError("id must be a unique nonempty string")
            if not isinstance(case["tenant"], str) or case["tenant"] not in {"alderbrook-law", "fernwick-llp"}:
                raise ValueError("unknown fixture tenant")
            if not isinstance(case["text"], str):
                raise ValueError("text must be a string")
            expected = case["expected"]
            if not isinstance(expected, dict) or set(expected) != set(FIELDS):
                raise ValueError("expected must contain exactly the three output fields")
            if any(value is not None and not isinstance(value, str) for value in expected.values()):
                raise ValueError("expected values must be strings or null")
            if expected["filing_type"] not in {None, "complaint", "motion", "order", "other"}:
                raise ValueError("unknown expected filing type")
            ids.add(case["id"])
            cases.append(case)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
    if len(cases) != 20:
        raise ValueError(f"expected exactly 20 notices; found {len(cases)}")
    return cases


def evaluate(cases, extractor=None):
    if not cases:
        raise ValueError("cannot evaluate an empty dataset")
    conn = connect(":memory:")
    correct = dict.fromkeys(FIELDS, 0)
    failures = []
    exact = 0
    try:
        init_db(conn)
        for case in cases:
            kwargs = {} if extractor is None else {"extractor": extractor}
            actual = run_extraction(case["text"], case["tenant"], conn, **kwargs)
            mismatched = [field for field in FIELDS if actual[field] != case["expected"][field]]
            for field in FIELDS:
                correct[field] += field not in mismatched
            exact += not mismatched
            if mismatched:
                failures.append(dict(id=case["id"], fields=mismatched, expected=case["expected"],
                                     actual={field: actual[field] for field in FIELDS}))
    finally:
        conn.close()
    accuracy = {field: count / len(cases) for field, count in correct.items()}
    return dict(total=len(cases), correct=correct, accuracy=accuracy,
                exact_match=exact / len(cases), threshold=THRESHOLD,
                passed=all(value >= THRESHOLD for value in accuracy.values()), failures=failures)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate(load_cases(args.data))
    except (OSError, ValueError) as exc:
        print(f"eval error: {exc}", file=sys.stderr)
        return 2
    for field in FIELDS:
        print(f"{field}: {report['correct'][field]}/{report['total']} = {report['accuracy'][field]:.2%}")
    print(f"exact_match: {report['exact_match']:.2%}")
    for failure in report["failures"]:
        print(json.dumps(failure, sort_keys=True))
    print(f"{'PASS' if report['passed'] else 'FAIL'} (each field must be >= {THRESHOLD:.0%})")
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
