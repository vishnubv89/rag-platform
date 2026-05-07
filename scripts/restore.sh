#!/usr/bin/env bash
# Restore the RAG database from a pg_dump custom-format backup.
# Usage: bash scripts/restore.sh [/path/to/rag_db_TIMESTAMP.pgdump]
#        If no path given, lists available backups and prompts for selection.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[restore]${NC} $*"; }
ok()   { echo -e "${GREEN}[restore]${NC} $*"; }
warn() { echo -e "${YELLOW}[restore]${NC} $*"; }
die()  { echo -e "${RED}[restore] ERROR:${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ── Select backup file ────────────────────────────────────────────────────────

if [ -n "${1:-}" ]; then
  BACKUP_FILE="$1"
  [ -f "$BACKUP_FILE" ] || die "File not found: $BACKUP_FILE"
else
  # List backups from the Docker volume via the backup container
  info "Available backups:"
  BACKUPS=$(docker compose run --rm --no-deps backup \
    sh -c "ls -1t /backups/rag_db_*.pgdump 2>/dev/null" 2>/dev/null) || true

  if [ -z "$BACKUPS" ]; then
    die "No backups found in the backups volume. Run scripts/backup.sh first."
  fi

  i=1
  while IFS= read -r line; do
    SIZE=$(docker compose run --rm --no-deps backup sh -c "du -sh '$line' | cut -f1" 2>/dev/null || echo "?")
    echo "  [$i] $(basename "$line")  ($SIZE)"
    i=$((i+1))
  done <<< "$BACKUPS"

  echo ""
  read -rp "Select backup number [1]: " CHOICE
  CHOICE="${CHOICE:-1}"
  BACKUP_FILE=$(echo "$BACKUPS" | sed -n "${CHOICE}p")
  [ -z "$BACKUP_FILE" ] && die "Invalid selection"
  info "Selected: $(basename "$BACKUP_FILE")"
fi

# ── Confirm ───────────────────────────────────────────────────────────────────

echo ""
warn "This will DROP and recreate the rag_db database, then restore from the backup."
warn "All current data will be lost."
echo ""
read -rp "Type 'yes' to continue: " CONFIRM
[ "$CONFIRM" = "yes" ] || { info "Aborted."; exit 0; }

# ── Stop dependent services ───────────────────────────────────────────────────

info "Stopping backend and admin-ui…"
docker compose stop backend admin-ui frontend 2>/dev/null || true

# ── Drop and recreate DB ──────────────────────────────────────────────────────

info "Dropping and recreating rag_db…"
docker compose exec -T postgres psql -U rag -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='rag_db' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker compose exec -T postgres psql -U rag -d postgres -c "DROP DATABASE IF EXISTS rag_db;" >/dev/null
docker compose exec -T postgres psql -U rag -d postgres -c "CREATE DATABASE rag_db OWNER rag;" >/dev/null
docker compose exec -T postgres psql -U rag -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
ok "Database recreated"

# ── Restore ───────────────────────────────────────────────────────────────────

info "Restoring from $(basename "$BACKUP_FILE")…"

if [[ "$BACKUP_FILE" == /backups/* ]] || [[ "$BACKUP_FILE" != /* ]]; then
  # File is inside the Docker volume — restore via the backup container
  docker compose run --rm --no-deps \
    -e PGHOST=postgres -e PGPORT=5432 -e PGUSER=rag -e PGPASSWORD=rag_secret \
    backup \
    sh -c "pg_restore --host=postgres --port=5432 --username=rag --dbname=rag_db --no-owner --role=rag '$BACKUP_FILE'"
else
  # Local file — pipe it into postgres via stdin
  docker compose exec -T postgres \
    pg_restore --username=rag --dbname=rag_db --no-owner < "$BACKUP_FILE"
fi

ok "Restore complete"

# ── Restart services ──────────────────────────────────────────────────────────

info "Restarting services…"
docker compose start backend admin-ui frontend 2>/dev/null || docker compose up -d

info "Waiting for backend…"
TRIES=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  TRIES=$((TRIES+1))
  [ $TRIES -ge 60 ] && die "backend did not come back healthy after 60s"
  sleep 2
done

ok "All services restored and healthy"
echo ""
echo -e "${GREEN}Restore successful.${NC} The database has been restored from:"
echo "  $(basename "$BACKUP_FILE")"
echo ""
