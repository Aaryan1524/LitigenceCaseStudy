import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.db import connect
from tests.support import ALDER, FERN, INVALID, TEXT, VALID, insert_notice, rows
from worker.run import run_once

ROOT = Path(__file__).resolve().parents[1]


def test_worker_claims_before_call_and_never_passes_tenant_context(db_path):
    insert_notice(db_path)
    calls = []
    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        assert rows(db_path)[0]["status"] == "processing"
        return dict(VALID)
    assert run_once(str(db_path), extractor=fake) == 1
    assert calls == [((TEXT,), {})]
    row = rows(db_path)[0]
    assert row["status"] == "pending"
    assert {key: row[key] for key in VALID} == VALID
    assert row["needs_review"] == 0


@pytest.mark.parametrize("answer", [None, {}, dict(VALID, matter_id="M-4410"),
                                    dict(VALID, filed_date="2026-02-30"), dict(VALID, filing_type="appeal")])
def test_invalid_extraction_is_persisted_pending_with_all_fields_null(db_path, answer):
    insert_notice(db_path)
    assert run_once(str(db_path), extractor=lambda text: answer) == 1
    row = rows(db_path)[0]
    assert row["status"] == "pending"
    assert {key: row[key] for key in INVALID} == INVALID


def test_extractor_error_does_not_abort_remaining_notices(db_path):
    insert_notice(db_path, "BAD", text="failure")
    insert_notice(db_path, "GOOD")
    def sometimes(text):
        if text == "failure":
            raise RuntimeError("synthetic extractor failure")
        return dict(VALID)
    assert run_once(str(db_path), extractor=sometimes) == 2
    result = rows(db_path)
    assert {key: result[0][key] for key in INVALID} == INVALID
    assert result[1]["matter_id"] == "M-3108"
    assert all(row["status"] == "pending" for row in result)


def test_worker_uses_each_rows_tenant_and_skips_nonreceived(db_path):
    insert_notice(db_path, "ALDER", text="Matter ID: M-4410. Motion.")
    insert_notice(db_path, "FERN", tenant=FERN, text="Matter ID: M-4410. Motion.")
    for status in ("processing", "pending", "docketed"):
        insert_notice(db_path, status, status=status)
    assert run_once(str(db_path)) == 2
    result = rows(db_path)
    assert result[0]["matter_id"] is None and result[0]["needs_review"] == 1
    assert result[1]["matter_id"] == "M-4410" and result[1]["needs_review"] == 0
    assert [row["status"] for row in result[2:]] == ["processing", "pending", "docketed"]
    assert run_once(str(db_path)) == 0
    assert rows(db_path, "calendar_entries") == []


def test_database_error_is_not_stored_as_invalid_answer(db_path, capsys):
    pk = insert_notice(db_path, "DB-ERROR")
    insert_notice(db_path, "UNTOUCHED")
    conn = connect(str(db_path))
    conn.execute("DROP TABLE matters")
    conn.close()
    with pytest.raises(sqlite3.Error):
        run_once(str(db_path))
    result = rows(db_path)
    assert result[0]["status"] == "processing"
    assert result[0]["needs_review"] == 0
    assert result[1]["status"] == "received"
    error = capsys.readouterr().err
    assert str(pk) in error and "matters" in error


def test_worker_cli_uses_environment_and_reports_count(db_path):
    insert_notice(db_path)
    env = dict(os.environ, LITIGENCE_DB=str(db_path))
    result = subprocess.run([sys.executable, "-m", "worker", "--once"], cwd=ROOT,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "processed 1"
    assert rows(db_path)[0]["status"] == "pending"


def test_worker_cli_database_failure_exits_one(db_path, conn):
    pk = insert_notice(db_path)
    conn.execute("DROP TABLE matters")
    result = subprocess.run([sys.executable, "-m", "worker", "--once", "--db", str(db_path)],
                            cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert str(pk) in result.stderr and "matters" in result.stderr
    assert rows(db_path)[0]["status"] == "processing"
