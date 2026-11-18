#!/usr/bin/env bash
# Start two workers at the same moment on N fresh notices; pass if their counts sum to N.
set -euo pipefail
N=${1:-200}
TMP=$(mktemp -d)
export LITIGENCE_DB="$TMP/two_workers.db"
python -c "from app.db import connect, init_db; init_db(connect())"
sqlite3 "$LITIGENCE_DB" "WITH RECURSIVE s(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM s WHERE i<$N)
  INSERT INTO notices(tenant_id, notice_id, text)
  SELECT 'alderbrook-law', 'TW-'||i, 'Notice of filing. Matter ID: M-3108. Order entered. Filed 2026-10-29.' FROM s;"
python -m worker --once > "$TMP/a.out" 2>&1 &
python -m worker --once > "$TMP/b.out" 2>&1 &
wait
A=$(tail -1 "$TMP/a.out" | awk '{print $2}')
B=$(tail -1 "$TMP/b.out" | awk '{print $2}')
PENDING=$(sqlite3 "$LITIGENCE_DB" "SELECT count(*) FROM notices WHERE status='pending'")
echo "worker A=$A worker B=$B sum=$((A + B)) notices=$N pending=$PENDING"
if [ $((A + B)) -eq "$N" ] && [ "$PENDING" -eq "$N" ]; then echo PASS; else echo FAIL; exit 1; fi
