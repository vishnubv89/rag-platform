#!/bin/sh
# Dumps the RAG database to /backups, keeping the last KEEP_DAYS days.
# Runs inside the rag_postgres container or any host with pg_dump + access.

set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="${BACKUP_DIR}/rag_db_${TIMESTAMP}.pgdump"

mkdir -p "$BACKUP_DIR"

echo "[backup] starting dump → $FILE"
pg_dump \
  --host="${PGHOST:-postgres}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER:-rag}" \
  --dbname="${PGDATABASE:-rag_db}" \
  --format=custom \
  --file="$FILE"

echo "[backup] dump complete ($(du -sh "$FILE" | cut -f1))"

# Prune backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "rag_db_*.pgdump" -mtime "+${KEEP_DAYS}" -delete
echo "[backup] pruned files older than ${KEEP_DAYS} days"
