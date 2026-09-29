#!/bin/sh
set -eu
interval="${BACKUP_INTERVAL_SECONDS:-86400}"
while true; do
  python /app/scripts/backup.py || true
  sleep "$interval"
done
