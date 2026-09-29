#!/bin/sh
set -eu
target="${1:-}"
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd); cd "$root"
if [ -z "$target" ] && [ -f releases/LAST_ROLLBACK_TARGET ]; then target=$(cat releases/LAST_ROLLBACK_TARGET); fi
[ -n "$target" ] || { echo "Usage: $0 releases/pre-deploy-YYYYMMDD-HHMMSS" >&2; exit 2; }
[ -d "$target" ] || { echo "Rollback target not found: $target" >&2; exit 2; }
mkdir -p backups
echo "Saving current database before code rollback..."
./scripts/backup-now.sh || true
echo "Stopping application services..."
docker compose stop quickboard backup || true
echo "Restoring application files from $target"
(cd "$target" && tar --exclude='./data' --exclude='./backups' --exclude='./releases' --exclude='./.env' -cf - .) | (cd "$root" && tar -xf -)
chmod +x scripts/*.sh
docker compose config >/dev/null
docker compose up -d --build --remove-orphans
url="https://${DOMAIN:-$(sed -n 's/^DOMAIN=//p' .env | tail -1)}"
i=0; until curl -fsS "$url/api/health" >/dev/null; do i=$((i+1)); [ "$i" -lt 12 ] || { echo "Rollback health check failed; inspect docker compose logs" >&2; exit 1; }; sleep 5; done
echo "Code rollback completed. Database was not changed. Use scripts/restore.sh only if a database rollback is explicitly required."
