#!/usr/bin/env bash
# Seed a temp db, insert one received notice, run the worker once, print the row.
set -euo pipefail
TMP=$(mktemp -d)
export LITIGENCE_DB="$TMP/smoke.db"
python -c "from app.db import connect, init_db; init_db(connect())"
sqlite3 "$LITIGENCE_DB" "INSERT INTO notices(tenant_id, notice_id, text) VALUES ('alderbrook-law', 'NTC-8841',
  'Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply.');"
python -m worker --once
sqlite3 -header -column "$LITIGENCE_DB" "SELECT notice_id, tenant_id, status, matter_id, filing_type, filed_date, needs_review FROM notices"
