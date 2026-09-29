#!/bin/sh
set -eu
snapshot="${1:-}"; database_backup="${2:-}"
[ -n "$snapshot" ] && [ -n "$database_backup" ] || { echo "Usage: $0 releases/pre-deploy-* backups/quickboard-*.db" >&2; exit 2; }
"$(dirname "$0")/rollback.sh" "$snapshot"
"$(dirname "$0")/restore.sh" "$database_backup"
