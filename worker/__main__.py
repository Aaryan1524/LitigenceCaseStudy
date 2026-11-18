"""`python -m worker --once`: drain received notices, last line `processed <n>`."""
import argparse
import sys

from worker.run import run_once


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m worker")
    parser.add_argument("--once", action="store_true", help="process all received notices, then exit")
    parser.add_argument("--db", default=None, help="database path (default: $LITIGENCE_DB or litigence.db)")
    args = parser.parse_args(argv)
    if not args.once:
        parser.error("only --once mode is supported")
    n = run_once(args.db)
    print(f"processed {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
