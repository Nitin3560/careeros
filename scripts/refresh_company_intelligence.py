import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.services.company_intelligence import (  # noqa: E402
    refresh_company_intelligence_from_jobs,
)


def main():
    db = SessionLocal()
    try:
        result = refresh_company_intelligence_from_jobs(db)
    finally:
        db.close()

    print(
        "company intelligence refreshed: "
        f"{result['companies']} companies, "
        f"{result['inserted']} inserted, "
        f"{result['refreshed']} refreshed"
    )


if __name__ == "__main__":
    main()
