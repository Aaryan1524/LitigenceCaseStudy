#!/usr/bin/env python3
"""Cross-check the two independently written suites against the same code.

1. The original agent-written suite (branch feat/tests) on main's application code.
2. The independent suite (tests/ on this branch) on the same code.
3. Each deliberate defect from scripts/mutation_check.py, applied to a disposable copy
   and run against the ORIGINAL suite: does the suite that never saw the code catch
   the defects the independent evaluator designed?

Writes evidence/cross-check.json. Never modifies this checkout.
Usage: python scripts/cross_check.py   (run from the repo root, with the four dependencies installed)
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ["app", "worker", "extractor"]


def sh(cmd, cwd=None):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)


def pytest_summary(cwd):
    r = sh(f"{sys.executable} -m pytest -p no:cacheprovider -o addopts= -q --tb=no", cwd=cwd)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]


def snapshot(tests_ref):
    d = Path(tempfile.mkdtemp()) / "snap"
    d.mkdir()
    sh(f"git archive HEAD {' '.join(APP)} | tar -x -C {d}", cwd=ROOT)
    if tests_ref:
        sh(f"git archive {tests_ref} tests | tar -x -C {d}", cwd=ROOT)
        (d / "pytest.ini").write_text("[pytest]\ntestpaths = tests\npythonpath = .\n")
    else:
        shutil.copytree(ROOT / "tests", d / "tests", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "evals", d / "evals", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "pytest.ini", d / "pytest.ini")
    return d


def main():
    spec = importlib.util.spec_from_file_location("mutation_check", ROOT / "scripts" / "mutation_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    original = snapshot("feat/tests")
    report = {
        "code_revision": sh("git rev-parse HEAD", cwd=ROOT).stdout.strip(),
        "original_suite_on_code": pytest_summary(original),
        "independent_suite_on_code": pytest_summary(snapshot(None)),
        "independent_mutations_vs_original_suite": [],
    }
    for mu in mod.MUTATIONS:
        d = Path(tempfile.mkdtemp()) / "m"
        shutil.copytree(original, d)
        f = d / mu["path"]
        text = f.read_text()
        if mu["old"] not in text:
            raise SystemExit(f"anchor changed for {mu['name']}")
        f.write_text(text.replace(mu["old"], mu["new"], 1))
        res = pytest_summary(d)
        report["independent_mutations_vs_original_suite"].append(
            {"mutation": mu["name"], "original_suite": res, "detected": "failed" in res})
    out = ROOT / "evidence" / "cross-check.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    detected = sum(m["detected"] for m in report["independent_mutations_vs_original_suite"])
    sys.exit(0 if detected == len(mod.MUTATIONS) else 1)


if __name__ == "__main__":
    main()
