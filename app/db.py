"""SQLite schema, seed and helpers (contract sections 2 and 4)."""
import os
import sqlite3

from app.constants import DB_ENV, DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants(
    tenant_id TEXT PRIMARY KEY,
    inbox TEXT UNIQUE NOT NULL,
    secret TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matters(
    tenant_id TEXT NOT NULL REFERENCES tenants,
    matter_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, matter_id)
);
CREATE TABLE IF NOT EXISTS notices(
    id INTEGER PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants,
    notice_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received',
    matter_id TEXT,
    filing_type TEXT,
    filed_date TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, notice_id)
);
CREATE TABLE IF NOT EXISTS calendar_entries(
    id INTEGER PRIMARY KEY,
    notice_pk INTEGER NOT NULL UNIQUE REFERENCES notices(id),
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    filed_date TEXT
);
"""

# Seed fixtures, exactly per contract section 2 (synthetic test data).
# Matter IDs are unique within a tenant only: the two M-3108 rows differ.
SEED_TENANTS = [
    ("alderbrook-law", "dockets@alderbrook-law.example", "alderbrook-fixture-key"),
    ("fernwick-llp", "dockets@fernwick-llp.example", "fernwick-fixture-key"),
]
SEED_MATTERS = [
    ("alderbrook-law", "M-3108"),
    ("alderbrook-law", "M-3109"),
    ("fernwick-llp", "M-3108"),
    ("fernwick-llp", "M-4410"),
]


def connect(path: str | None = None) -> sqlite3.Connection:
    if path is None:
        path = os.environ.get(DB_ENV, DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn) -> None:
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO tenants(tenant_id, inbox, secret) VALUES (?, ?, ?)",
        SEED_TENANTS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO matters(tenant_id, matter_id) VALUES (?, ?)",
        SEED_MATTERS,
    )
    if conn.in_transaction:
        conn.commit()


def matter_ids(conn, tenant_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT matter_id FROM matters WHERE tenant_id = ?", (tenant_id,)
    ).fetchall()
    return {r[0] for r in rows}
