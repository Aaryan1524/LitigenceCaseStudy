"""Run independent tests and evals; preserve evidence under reports/."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    manifest = json.loads((reports / "source-manifest.json").read_text())
    changed = [name for name, digest in manifest["files"].items()
               if not (ROOT / name).exists()
               or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    if changed:
        print("Source differs from the frozen snapshot: " + ", ".join(changed), file=sys.stderr)
        return 2
    commands = [
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         f"--junitxml={reports / 'tests.xml'}"],
        [sys.executable, "-m", "evals", "--json-report", str(reports / "evals.json")],
    ]
    runs = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        runs.append(dict(command=command, returncode=result.returncode,
                         stdout=result.stdout, stderr=result.stderr))
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                            capture_output=True, text=True, timeout=15, check=True)
    (reports / "environment.txt").write_text(freeze.stdout)
    tests_ran = 0
    if (reports / "tests.xml").exists():
        tests_ran = sum(int(suite.get("tests", "0"))
                        for suite in ET.parse(reports / "tests.xml").getroot().iter("testsuite"))
    report = dict(time_utc=datetime.now(timezone.utc).isoformat(),
                  revision=manifest["revision"], python=platform.python_version(),
                  platform=platform.platform(), source_unchanged=True,
                  tests_ran=tests_ran, runs=runs,
                  passed=tests_ran > 0 and all(run["returncode"] == 0 for run in runs))
    (reports / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
