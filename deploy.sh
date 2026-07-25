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

echo "=== Industrial Park Agent v1.2 Deploy ==="
echo "  path: $(pwd)"
echo "  time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

case "${1:-up}" in
  build)
    echo "[1/3] Stopping existing containers..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

    echo "[2/3] Building images..."
    docker compose -f "$COMPOSE_FILE" build --no-cache

    echo "[3/3] Starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    ;;

  up)
    echo "[1/2] Pulling base images..."
    docker compose -f "$COMPOSE_FILE" pull postgres redis nginx 2>/dev/null || true

    echo "[2/2] Starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    ;;

  down)
    docker compose -f "$COMPOSE_FILE" down
    echo "All services stopped."
    ;;

  logs)
    docker compose -f "$COMPOSE_FILE" logs -f --tail=50 "${2:-}"
    ;;

  status)
    docker compose -f "$COMPOSE_FILE" ps
    ;;

  health)
    echo "=== Health Check ==="
    # Backend
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
      echo "  ✅ Backend :8000 — healthy"
    else
      echo "  ❌ Backend :8000 — not responding"
    fi
    # Frontend
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
      echo "  ✅ Frontend :3000 — healthy"
    else
      echo "  ⚠️  Frontend :3000 — check logs"
    fi
    # Postgres
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U industrial -d industrial_park > /dev/null 2>&1; then
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
