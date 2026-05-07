#!/usr/bin/env bash
# One-click deploy for the RAG platform.
# Usage: bash scripts/deploy.sh [--no-build] [--reset-db]
#
# --no-build  skip docker compose build (use existing images)
# --reset-db  drop and recreate the postgres volume before starting

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[deploy]${NC} $*"; }
ok()    { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
die()   { echo -e "${RED}[deploy] ERROR:${NC} $*" >&2; exit 1; }

NO_BUILD=false
RESET_DB=false
for arg in "$@"; do
  case $arg in
    --no-build) NO_BUILD=true ;;
    --reset-db) RESET_DB=true ;;
    *) die "Unknown flag: $arg" ;;
  esac
done

# ── Prerequisites ────────────────────────────────────────────────────────────

command -v docker   >/dev/null 2>&1 || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "docker compose (v2) is not installed"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ── .env setup ───────────────────────────────────────────────────────────────

if [ ! -f .env ]; then
  info ".env not found — generating from .env.example"
  if [ ! -f .env.example ]; then
    cat > .env.example <<'EXAMPLE'
# Required — get from https://aistudio.google.com/apikey
GOOGLE_API_KEY=

# Random secrets — generate with: openssl rand -hex 32
JWT_SECRET=
ADMIN_SECRET_KEY=

# Backup retention (days) and interval (hours)
BACKUP_KEEP_DAYS=7
BACKUP_INTERVAL_HOURS=24
EXAMPLE
  fi
  cp .env.example .env

  echo ""
  warn "Please fill in the required values in .env:"
  echo ""

  prompt_secret() {
    local key=$1 label=$2
    local val
    read -rsp "  ${label}: " val; echo ""
    [ -z "$val" ] && die "${key} cannot be empty"
    # Replace the placeholder line in .env
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
  }

  prompt_plain() {
    local key=$1 label=$2 default=$3
    local val
    read -rp "  ${label} [${default}]: " val
    val="${val:-$default}"
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
  }

  prompt_secret "GOOGLE_API_KEY"     "Google AI API key (https://aistudio.google.com/apikey)"
  prompt_secret "JWT_SECRET"         "JWT secret (or press enter to auto-generate)" || \
    { JWT_AUTO=$(openssl rand -hex 32); sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_AUTO}|" .env && rm -f .env.bak; ok "JWT_SECRET auto-generated"; }
  prompt_secret "ADMIN_SECRET_KEY"   "Admin secret key (or press enter to auto-generate)" || \
    { ADMIN_AUTO=$(openssl rand -hex 24); sed -i.bak "s|^ADMIN_SECRET_KEY=.*|ADMIN_SECRET_KEY=${ADMIN_AUTO}|" .env && rm -f .env.bak; ok "ADMIN_SECRET_KEY auto-generated"; }
  echo ""
fi

# Auto-generate secrets if still placeholder/empty
_fill_secret() {
  local key=$1
  local current
  current=$(grep "^${key}=" .env | cut -d= -f2-)
  if [ -z "$current" ] || [ "$current" = "change-me" ] || echo "$current" | grep -q "change-me"; then
    local val
    val=$(openssl rand -hex 32)
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
    warn "${key} was empty/placeholder — auto-generated"
  fi
}

_fill_secret JWT_SECRET
_fill_secret ADMIN_SECRET_KEY

# Validate GOOGLE_API_KEY is set
GOOGLE_API_KEY=$(grep "^GOOGLE_API_KEY=" .env | cut -d= -f2-)
[ -z "$GOOGLE_API_KEY" ] && die "GOOGLE_API_KEY is not set in .env"

# ── Optional DB reset ─────────────────────────────────────────────────────────

if [ "$RESET_DB" = true ]; then
  warn "--reset-db: stopping services and wiping postgres volume"
  docker compose down -v --remove-orphans 2>/dev/null || true
  ok "Volumes removed"
fi

# ── Build ─────────────────────────────────────────────────────────────────────

if [ "$NO_BUILD" = false ]; then
  info "Building images (this may take a few minutes)…"
  docker compose build --parallel
  ok "Build complete"
fi

# ── Start services ────────────────────────────────────────────────────────────

info "Starting services…"
docker compose up -d --remove-orphans

# ── Wait for postgres ─────────────────────────────────────────────────────────

info "Waiting for postgres to be ready…"
TRIES=0
until docker compose exec -T postgres pg_isready -U rag -d rag_db >/dev/null 2>&1; do
  TRIES=$((TRIES+1))
  [ $TRIES -ge 30 ] && die "postgres did not become ready after 30s"
  sleep 1
done
ok "Postgres ready"

# ── Run migrations ────────────────────────────────────────────────────────────

info "Applying migrations…"
for f in $(ls backend/src/rag_chatbot/db/migrations/*.sql | sort); do
  name=$(basename "$f")
  docker compose exec -T postgres psql -U rag -d rag_db -f - < "$f" >/dev/null 2>&1 && \
    ok "  ✓ $name" || warn "  ⚠ $name (may already be applied)"
done

# ── Wait for backend ──────────────────────────────────────────────────────────

info "Waiting for backend to be healthy…"
TRIES=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  TRIES=$((TRIES+1))
  [ $TRIES -ge 60 ] && die "backend did not become healthy after 60s"
  sleep 2
done
ok "Backend healthy"

# ── Print summary ─────────────────────────────────────────────────────────────

ADMIN_KEY=$(grep "^ADMIN_SECRET_KEY=" .env | cut -d= -f2-)

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        RAG Platform is live 🎉                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Chat UI      ${NC}→  http://localhost:5173"
echo -e "  ${CYAN}Admin UI     ${NC}→  http://localhost:8080"
echo -e "  ${CYAN}Backend API  ${NC}→  http://localhost:8000/docs  (disabled in prod)"
echo -e "  ${CYAN}Admin key    ${NC}→  ${ADMIN_KEY}"
echo ""
echo -e "  Logs:    docker compose logs -f"
echo -e "  Stop:    docker compose down"
echo -e "  Backup:  bash scripts/backup.sh"
echo -e "  Restore: bash scripts/restore.sh"
echo ""
