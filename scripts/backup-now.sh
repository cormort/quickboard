#!/bin/sh
set -eu
docker compose run --rm backup python /app/scripts/backup.py
