#!/bin/bash
# ═════════════════════════════════════════════════════
# Industrial Park Agent v1.2 — Production Deploy Script
# ═════════════════════════════════════════════════════
# Usage: ./deploy.sh [build|up|down|logs|status|health]
# Server: RainYun Ubuntu 22.04, path /www/wwwroot/industrial-park/

set -euo pipefail

DEPLOY_DIR="/www/wwwroot/industrial-park"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env.production"

cd "$DEPLOY_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.production.example and replace all placeholders." >&2
  exit 1
fi

export ENV_FILE

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

echo "=== Industrial Park Agent v1.2 Deploy ==="
echo "  path: $(pwd)"
echo "  time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

case "${1:-up}" in
  build)
    echo "[1/3] Stopping existing containers..."
    compose down --remove-orphans 2>/dev/null || true

    echo "[2/3] Building images..."
    compose build --no-cache

    echo "[3/3] Starting services..."
    compose up -d
    ;;

  up)
    echo "[1/2] Pulling base images..."
    compose pull postgres redis nginx 2>/dev/null || true

    echo "[2/2] Starting services..."
    compose up -d --build
    ;;

  down)
    compose down
    echo "All services stopped."
    ;;

  logs)
    compose logs -f --tail=50 "${2:-}"
    ;;

  status)
    compose ps
    ;;

  health)
    echo "=== Health Check ==="
    # Backend
    if curl -sf http://localhost:8080/api/v1/health/ready > /dev/null 2>&1; then
      echo "  ✅ Backend readiness via :8080 — ready"
    else
      echo "  ❌ Backend readiness via :8080 — not ready"
    fi
    # Frontend
    if curl -sf http://localhost:8080 > /dev/null 2>&1; then
      echo "  ✅ Frontend via :8080 — healthy"
    else
      echo "  ⚠️  Frontend :3000 — check logs"
    fi
    # Postgres
    if compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /dev/null 2>&1; then
      echo "  ✅ Postgres — ready"
    else
      echo "  ❌ Postgres — not ready"
    fi
    ;;

  *)
    echo "Usage: ./deploy.sh {build|up|down|logs|status|health}"
    exit 1
    ;;
esac

echo ""
echo "Done. $(date -u +%H:%M:%S)"
