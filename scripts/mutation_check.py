"""Prove selected safety tests fail for known defects, using disposable copies."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    dict(name="signature-bypass", path="app/main.py",
         old="or not hmac.compare_digest(sig.lower(), expected)", new="or False",
         test="tests/test_http.py::test_other_tenant_key_cannot_authorize_delivery"),
    dict(name="sign-reserialized-json", path="app/main.py",
         old='tenant["secret"].encode(), raw, hashlib.sha256',
         new='tenant["secret"].encode(), json.dumps(payload).encode(), hashlib.sha256',
         test="tests/test_http.py::test_published_signature_example"),
    dict(name="cross-tenant-matter-lookup", path="worker/checks.py",
         old="known = matter_ids(conn, tenant_id)",
         new='known = matter_ids(conn, "fernwick-llp") | matter_ids(conn, "alderbrook-law")',
         test="tests/test_validation.py::test_other_tenant_exclusive_matter_is_rejected"),
    dict(name="claim-already-processing-notice", path="worker/run.py",
         old="WHERE status='received' ORDER BY id LIMIT 1)\n  AND status='received'",
         new="WHERE status IN ('received','processing') ORDER BY id LIMIT 1)\n  AND status IN ('received','processing')",
         test="tests/test_concurrency.py::test_two_workers_extract_each_notice_exactly_once"),
    dict(name="nontransactional-approval", path="app/main.py",
         old='conn.execute("BEGIN IMMEDIATE")', new='conn.execute("SELECT 1")',
         test="tests/test_http.py::test_approval_rolls_back_calendar_if_status_update_fails"),
    dict(name="swallow-database-lookup-error", path="worker/checks.py",
         old="known = matter_ids(conn, tenant_id)",
         new="try:\n            known = matter_ids(conn, tenant_id)\n        except Exception:\n            return _invalid()",
         test="tests/test_validation.py::test_database_lookup_error_propagates"),
    dict(name="accept-impossible-calendar-date", path="worker/checks.py",
         old="not _real_date(filed_date)", new="False",
         test="tests/test_worker.py::test_invalid_extraction_is_persisted_pending_with_all_fields_null"),
]


def copy_snapshot(target):
    for folder in ("app", "worker", "extractor", "tests", "evals"):
        shutil.copytree(ROOT / folder, target / folder,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    shutil.copy2(ROOT / "pytest.ini", target / "pytest.ini")


def pytest_run(target, selection):
    xml = target / "result.xml"
    result = subprocess.run([
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        f"--junitxml={xml}", *selection,
    ], cwd=target, capture_output=True, text=True, timeout=45)
    totals = dict(tests=0, failures=0, errors=0)
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in totals:
                totals[key] += int(suite.get(key, "0"))
    return dict(returncode=result.returncode, **totals,
                stdout=result.stdout, stderr=result.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-report", type=Path, default=ROOT / "reports/mutations.json")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="litigence-baseline-") as folder:
        target = Path(folder)
        copy_snapshot(target)
        baseline = pytest_run(target, sorted({case["test"] for case in MUTATIONS}))
    if baseline["returncode"] != 0 or baseline["tests"] == 0:
        print("ERROR: selected baseline tests must pass before mutation", file=sys.stderr)
        print(baseline["stdout"], file=sys.stderr)
        print(baseline["stderr"], file=sys.stderr)
        return 2
    results = []
    for mutation in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="litigence-mutant-") as folder:
            target = Path(folder)
            copy_snapshot(target)
            source = target / mutation["path"]
            original = source.read_text()
            if original.count(mutation["old"]) != 1:
                raise RuntimeError(f"mutation anchor changed: {mutation['name']}")
            source.write_text(original.replace(mutation["old"], mutation["new"], 1))
            result = pytest_run(target, [mutation["test"]])
            # Syntax/import failures do not count as detecting the behavioral defect.
            killed = result["returncode"] == 1 and result["failures"] > 0 and result["errors"] == 0
            results.append(dict(name=mutation["name"], test=mutation["test"], killed=killed, **result))
            print(f"{'DETECTED' if killed else 'NOT DETECTED'}: {mutation['name']}")
    count = sum(result["killed"] for result in results)
    report = dict(total=len(results), detected=count, baseline=baseline, mutations=results)
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{count}/{len(results)} selected defects detected")
    return 0 if count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
