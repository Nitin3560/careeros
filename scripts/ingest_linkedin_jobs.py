import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.services.job_ingestion.linkedin import fetch_linkedin_jobs  # noqa: E402
from app.services.job_ingestion.persist import save_jobs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="software-engineer")
    args = parser.parse_args()

    jobs = fetch_linkedin_jobs(args.query)
    db = SessionLocal()
    try:
        result = save_jobs(db, jobs)
    finally:
        db.close()

    print(f"fetched {len(jobs)} linkedin jobs")
    print(f"inserted {result['inserted']}")
    print(f"skipped {result['skipped']}")


if __name__ == "__main__":
    main()
