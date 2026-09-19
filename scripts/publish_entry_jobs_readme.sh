#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"
SINCE_HOURS="${SINCE_HOURS:-168}"
LIMIT="${LIMIT:-100}"
BOARD_LIMIT="${BOARD_LIMIT:-100}"
BOARD_PRIORITY="${BOARD_PRIORITY:-1}"
README_PATH="${README_PATH:-$ROOT/README.md}"

cd "$ROOT"

"$PYTHON_BIN" scripts/backfill_jobs.py --priority "$BOARD_PRIORITY" --stale-days 0 --limit "$BOARD_LIMIT"
"$PYTHON_BIN" - <<'PY'
import sys
sys.path.insert(0, 'apps/api')
from app.database import SessionLocal
from app.services.job_ingestion.amazon import fetch_amazon_jobs
from app.services.job_ingestion.persist import save_jobs

db = SessionLocal()
try:
    jobs = fetch_amazon_jobs('software-development-engineer')
    result = save_jobs(db, jobs)
    print({'amazon_fetched': len(jobs), **result})
finally:
    db.close()
PY
"$PYTHON_BIN" scripts/apply_title_filter.py --version v3 --new-only --since-minutes "$((SINCE_HOURS * 60))" --review-limit 10
"$PYTHON_BIN" scripts/update_entry_jobs_readme.py --readme "$README_PATH" --since-hours "$SINCE_HOURS" --limit "$LIMIT"

if git diff --quiet -- "$README_PATH"; then
  echo "README unchanged; nothing to publish."
  exit 0
fi

git add "$README_PATH"
git commit -m "Update entry-level job README feed"
git push
