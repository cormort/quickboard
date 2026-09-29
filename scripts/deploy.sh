#!/bin/sh
set -eu
release="${1:-}"
[ -n "$release" ] || { echo "Usage: $0 /path/to/new-release-directory" >&2; exit 2; }
[ -d "$release" ] || { echo "Release directory not found: $release" >&2; exit 2; }
for f in docker-compose.yml Dockerfile requirements.txt app/main.py; do [ -f "$release/$f" ] || { echo "Missing release file: $f" >&2; exit 2; }; done
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd); cd "$root"
stamp=$(date +%Y%m%d-%H%M%S); snapshot="releases/pre-deploy-$stamp"; mkdir -p "$snapshot" backups releases
[ -f .env ] || { echo ".env is missing" >&2; exit 2; }
echo "[1/7] Creating database backup"
./scripts/backup-now.sh
echo "[2/7] Saving current application snapshot: $snapshot"
tar --exclude='./data' --exclude='./backups' --exclude='./releases' --exclude='./.env' -cf - . | tar -xf - -C "$snapshot"
echo "[3/7] Copying new release while preserving .env/data/backups"
tar --exclude='./data' --exclude='./backups' --exclude='./releases' --exclude='./.env' -cf - -C "$release" . 2>/dev/null | tar -xf - -C "$root" 2>/dev/null || {
  (cd "$release" && tar --exclude='./data' --exclude='./backups' --exclude='./releases' --exclude='./.env' -cf - .) | (cd "$root" && tar -xf -)
}
chmod +x scripts/*.sh
echo "[4/7] Validating Compose"
docker compose config >/dev/null
echo "[5/7] Building images"
docker compose build --pull quickboard backup
echo "[6/7] Starting services"
docker compose up -d --remove-orphans
url="https://${DOMAIN:-$(sed -n 's/^DOMAIN=//p' .env | tail -1)}"
echo "[7/7] Health check: $url/api/health"
i=0; until curl -fsS "$url/api/health" >/dev/null; do i=$((i+1)); [ "$i" -lt 12 ] || { echo "Deployment health check failed, rolling back" >&2; exec "$root/scripts/rollback.sh" "$snapshot"; }; sleep 5; done
echo "$snapshot" > releases/LAST_ROLLBACK_TARGET
echo "Deployment completed. Rollback target: $snapshot"
