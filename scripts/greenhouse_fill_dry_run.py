import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.services.greenhouse_filler import run_greenhouse_dry_run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run fill a ready Greenhouse application packet; never submits.")
    parser.add_argument("--packet-id")
    parser.add_argument("--job-id")
    parser.add_argument("--profile-version", type=int, default=1)
    parser.add_argument("--output-dir", default="generated/greenhouse_dry_runs")
    parser.add_argument("--submit", action="store_true", help="Reserved for future use; currently always rejected.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = run_greenhouse_dry_run(
            db,
            packet_id=args.packet_id,
            job_id=args.job_id,
            profile_version=args.profile_version,
            output_dir=args.output_dir,
            submit=args.submit,
        )
        print(json.dumps(result, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
