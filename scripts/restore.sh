#!/bin/sh
set -eu
backup="${1:-}"
[ -n "$backup" ] || { echo "Usage: $0 backups/quickboard-YYYYMMDD-HHMMSS.db" >&2; exit 2; }
[ -f "$backup" ] || { echo "Backup not found: $backup" >&2; exit 2; }
python3 - "$backup" <<'PY'
import sqlite3,sys
p=sys.argv[1]; c=sqlite3.connect(f'file:{p}?mode=ro',uri=True); r=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close()
if r!='ok': raise SystemExit(f'Integrity check failed: {r}')
print('Integrity check: ok')
PY
stamp=$(date +%Y%m%d-%H%M%S)
echo "Stopping QuickBoard..."
docker compose stop quickboard backup
[ ! -f data/quickboard.db ] || cp -p data/quickboard.db "backups/pre-restore-$stamp.db"
cp "$backup" data/quickboard.db
rm -f data/quickboard.db-wal data/quickboard.db-shm
chmod 600 data/quickboard.db || true
docker compose up -d quickboard backup caddy
sleep 5
docker compose exec -T quickboard python - <<'PY'
import sqlite3
c=sqlite3.connect('/data/quickboard.db'); print('Restored DB:',c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()
PY
echo "Restore completed. Pre-restore copy: backups/pre-restore-$stamp.db"
