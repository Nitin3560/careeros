#!/usr/bin/env python3
import os
from pathlib import Path
import sys
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402


def enabled() -> bool:
    return os.getenv("POLLER_RETENTION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def main() -> None:
    if not enabled():
        print("retention disabled")
        return
    db = SessionLocal()
    try:
        completed = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM poll_runs WHERE finished_at IS NOT NULL)
               AND NOT EXISTS (
                   SELECT 1 FROM ats_boards
                   WHERE status <> 'dead' AND last_success_at IS NULL
               )
        """)).scalar_one()
        if not completed:
            raise SystemExit("retention guard: no full successful sweep recorded")
        ids = db.execute(text("""
            SELECT j.id FROM jobs j
            WHERE j.expired_at < now() - interval '90 days'
              AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id=j.id)
              AND NOT EXISTS (SELECT 1 FROM resume_versions r WHERE r.job_id=j.id)
        """)).scalars().all()
        if ids:
            db.execute(text("DELETE FROM job_matches WHERE job_id = ANY(:ids)"), {"ids": ids})
            result = db.execute(text("DELETE FROM jobs WHERE id = ANY(:ids)"), {"ids": ids})
        else:
            result = None
        db.commit()
        print(f"deleted_jobs={(result.rowcount if result else 0) or 0}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
