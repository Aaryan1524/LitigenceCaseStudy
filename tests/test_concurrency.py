from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.support import ALDER, insert_notice, rows

ROOT = Path(__file__).resolve().parents[1]


def run_pair(kind, db_path, scratch):
    scratch.mkdir()
    processes = []
    def wait_for_all(suffix):
        deadline = time.monotonic() + 15
        while not all((scratch / f"{name}.{suffix}").exists() for name in ("a", "b")):
            for process in processes:
                if process.poll() is not None:
                    out, err = process.communicate()
                    pytest.fail(f"probe exited before {suffix}: {process.returncode}\n{out}\n{err}")
            if time.monotonic() >= deadline:
                pytest.fail(f"processes did not reach {suffix} barrier")
            time.sleep(0.01)
    try:
        for name in ("a", "b"):
            processes.append(subprocess.Popen(
                [sys.executable, str(ROOT / "tests/concurrency_probe.py"), kind,
                 str(db_path), str(scratch), name], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        wait_for_all("ready")
        (scratch / "release").touch()
        if kind == "worker":
            wait_for_all("extracting")
            (scratch / "extraction-release").touch()
        for process in processes:
            out, err = process.communicate(timeout=20)
            assert process.returncode == 0, f"{out}\n{err}"
        return [json.loads((scratch / f"{name}.json").read_text()) for name in ("a", "b")]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate()


def test_two_simultaneous_intakes_store_one_original(db_path, tmp_path):
    results = run_pair("intake", db_path, tmp_path / "intake-race")
    assert [r["status"] for r in results] == [200, 200]
    stored = rows(db_path)
    assert len(stored) == 1
    assert stored[0]["text"] in {"original from a", "original from b"}
    assert stored[0]["status"] == "received"


def test_two_workers_extract_each_notice_exactly_once(db_path, tmp_path):
    texts = [f"synthetic-notice-{i}" for i in range(18)]
    for index, text in enumerate(texts):
        insert_notice(db_path, f"RACE-{index}", text=text)
    results = run_pair("worker", db_path, tmp_path / "worker-race")
    assert all(result["count"] >= 1 for result in results), "both workers must participate"
    assert sum(result["count"] for result in results) == len(texts)
    assert Counter(text for result in results for text in result["calls"]) == Counter(texts)
    assert len(rows(db_path)) == len(texts)
    assert all(row["status"] == "pending" for row in rows(db_path))


def test_two_simultaneous_approvals_create_one_calendar_entry(db_path, tmp_path):
    pk = insert_notice(db_path, status="pending", matter_id="M-3108", needs_review=1)
    results = run_pair("approve", db_path, tmp_path / "approve-race")
    assert [r["status"] for r in results] == [200, 200]
    calendar = rows(db_path, "calendar_entries")
    assert len(calendar) == 1
    assert calendar[0]["notice_pk"] == pk
    assert calendar[0]["tenant_id"] == ALDER
    assert rows(db_path)[0]["status"] == "docketed"
    assert rows(db_path)[0]["needs_review"] == 0
