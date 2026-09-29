#!/bin/sh
set -eu
docker compose run --rm backup python /app/scripts/notify.py "QuickBoard notification test" "This is a test notification from QuickBoard backup service." "test"
