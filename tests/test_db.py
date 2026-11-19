import sqlite3

import pytest

from app.db import connect, init_db, matter_ids
from tests.support import ALDER, FERN, insert_notice


def test_connection_pragmas_and_row_factory(conn):
    assert conn.row_factory is sqlite3.Row
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_seed_is_idempotent_and_tenant_scoped(conn):
    init_db(conn)
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM matters").fetchone()[0] == 4
    assert matter_ids(conn, ALDER) == {"M-3108", "M-3109"}
    assert matter_ids(conn, FERN) == {"M-3108", "M-4410"}
    assert matter_ids(conn, "missing") == set()


def test_environment_selects_database(db_path, monkeypatch):
    monkeypatch.setenv("LITIGENCE_DB", str(db_path))
    conn = connect()
    try:
        assert matter_ids(conn, ALDER) == {"M-3108", "M-3109"}
    finally:
        conn.close()


def test_notice_uniqueness_is_enforced_by_database_per_tenant(db_path):
    insert_notice(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_notice(db_path)
    insert_notice(db_path, tenant=FERN)


def test_calendar_uniqueness_is_enforced_by_database(db_path, conn):
    pk = insert_notice(db_path)
    values = (pk, ALDER, "M-3108")
    sql = "INSERT INTO calendar_entries(notice_pk, tenant_id, matter_id) VALUES (?, ?, ?)"
    conn.execute(sql, values)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, values)


def test_foreign_keys_reject_unknown_tenant(db_path):
    with pytest.raises(sqlite3.IntegrityError):
        insert_notice(db_path, tenant="missing")
