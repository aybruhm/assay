#!/usr/bin/env bash
# Phase 1 exit check, also the script for the Phase 4 demo recording.
# Requires: docker compose up -d db
set -euo pipefail

DB_URL="${PLANNER_DB_URL:-postgresql://planner:planner@localhost:5432/planner}"
TID="demo-$(date +%s)"

echo "1. Run, then get killed during narration."
set +e
PLANNER_CRASH_AT=narrate PLANNER_FAKE_MODEL=1 PLANNER_FAKE_SINK=1 PLANNER_DB_URL="$DB_URL" \
  python -m planner.cli run "$TID" "I earn 45,000 a year in England" --date 2026-10-01
code=$?
set -e
test "$code" -eq 137 || { echo "expected exit 137, got $code"; exit 1; }
echo "   (killed with 137 as narrate started)"

echo "2. Resume with the same thread_id."
PLANNER_FAKE_MODEL=1 PLANNER_FAKE_SINK=1 PLANNER_DB_URL="$DB_URL" python -m planner.cli resume "$TID"

echo "3. History:"
PLANNER_DB_URL="$DB_URL" python -m planner.cli history "$TID"
