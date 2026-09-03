import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

ATS_MAP = {
    "amazon": "amazon",
    "greenhouse": "greenhouse",
    "lever": "lever",
    "ashby": "ashby",
    "smartrecruiters": "smartrecruiters",
    "workable": "workable",
}


def load_boards(path: str) -> list[tuple[str, str]]:
    data = json.load(open(path))
    pairs = []
    for raw_ats, slugs in data.items():
        ats = ATS_MAP.get(raw_ats.lower())
        if not ats:
            print(f"skipping unknown ats: {raw_ats}")
            continue
        for slug in slugs:
            if isinstance(slug, dict):
                slug = slug.get("slug") or slug.get("name")
            if slug:
                pairs.append((ats, str(slug).strip()))
    return pairs


def main(path: str):
    pairs = load_boards(path)
    print(f"parsed {len(pairs)} boards from {path}")

    db = SessionLocal()
    try:
        before = db.scalar(select(func.count()).select_from(models.AtsBoard))
        for index in range(0, len(pairs), 1000):
            chunk = pairs[index : index + 1000]
            stmt = (
                insert(models.AtsBoard)
                .values(
                    [
                        {
                            "ats": ats,
                            "slug": slug,
                            "status": "unknown",
                            "source_list": "job-boards-archive",
                        }
                        for ats, slug in chunk
                    ]
                )
                .on_conflict_do_nothing(index_elements=["ats", "slug"])
            )
            db.execute(stmt)
            db.commit()
            print(f"{min(index + 1000, len(pairs))}/{len(pairs)}")

        after = db.scalar(select(func.count()).select_from(models.AtsBoard))
        print(f"\nats_boards: {before} -> {after} (+{after - before} new)")

        rows = (
            db.query(models.AtsBoard.ats, func.count(models.AtsBoard.id))
            .group_by(models.AtsBoard.ats)
            .order_by(models.AtsBoard.ats)
            .all()
        )
        for ats, count in rows:
            print(f"{ats:<16} {count}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/import_boards.py /path/to/boards.json")
    main(sys.argv[1])
