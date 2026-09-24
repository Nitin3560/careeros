#!/usr/bin/env python3
"""Acknowledge the current classified feed for the NEW marker."""
import sys
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("UPDATE job_feed_state SET last_viewed_at=now(), updated_at=now() WHERE id=1"))
        db.commit()
        print("Feed marked viewed; jobs first seen after now will be marked NEW.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
