"""Worker loop: atomic claim, shared check, finish (contract sections 3 and 6)."""
from app.db import connect
from extractor import extract
from worker.checks import Extractor, run_extraction

CLAIM_SQL = """
UPDATE notices SET status='processing'
WHERE id = (SELECT id FROM notices WHERE status='received' ORDER BY id LIMIT 1)
  AND status='received'
RETURNING id, tenant_id, text
"""

FINISH_SQL = """
UPDATE notices SET status='pending', matter_id=?, filing_type=?, filed_date=?, needs_review=?
WHERE id=? AND status='processing'
"""


def _claim(conn):
    # One statement; the database decides who wins. fetchall() steps the
    # statement to completion so the autocommit transaction ends here.
    rows = conn.execute(CLAIM_SQL).fetchall()
    if conn.in_transaction:
        conn.commit()
    return rows[0] if rows else None


def run_once(db_path: str | None = None, extractor: Extractor = extract) -> int:
    """Process received notices until a fresh claim finds nothing. Returns the count."""
    conn = connect(db_path)
    processed = 0
    try:
        while True:
            row = _claim(conn)
            if row is None:
                break
            result = run_extraction(row["text"], row["tenant_id"], conn, extractor)
            conn.execute(
                FINISH_SQL,
                (
                    result["matter_id"],
                    result["filing_type"],
                    result["filed_date"],
                    1 if result["needs_review"] else 0,
                    row["id"],
                ),
            )
            if conn.in_transaction:
                conn.commit()
            processed += 1
    finally:
        conn.close()
    return processed
