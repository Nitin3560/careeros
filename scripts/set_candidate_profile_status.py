import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

VALID_STATUSES = {"ACTIVE", "SUPERSEDED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        profile = (
            db.query(models.CandidateProfile)
            .filter(models.CandidateProfile.user_id == args.user_id)
            .first()
        )
        if not profile:
            raise SystemExit("candidate profile not found")
        profile.status = args.status
        db.commit()
        print(f"candidate profile {args.user_id} -> {args.status}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
