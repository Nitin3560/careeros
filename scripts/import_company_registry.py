#!/usr/bin/env python3
"""Import target companies into the Phase 1B registry."""
import argparse
import csv
from pathlib import Path
import re
import sys
import uuid

from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.models import CompanyRegistry  # noqa: E402


def parse_tags(value: str | None) -> list[str]:
    return sorted({part.strip().lower() for part in re.split(r"[,;|]", value or "") if part.strip()})


def clean_row(row: dict[str, str]) -> dict:
    name = (row.get("company_name") or "").strip()
    if not name:
        raise ValueError("company_name is required")
    return {
        "company_name": name,
        "domain": (row.get("domain") or "").strip().lower() or None,
        "careers_url": (row.get("careers_url") or "").strip() or None,
        "source_tags": parse_tags(row.get("source_tags")),
        "priority": int((row.get("priority") or "3").strip()),
    }


def import_rows(db, rows) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for raw in rows:
        item = clean_row(raw)
        existing = db.query(CompanyRegistry).filter(
            func.lower(CompanyRegistry.company_name) == item["company_name"].lower(),
            func.coalesce(CompanyRegistry.domain, "") == (item["domain"] or ""),
        ).one_or_none()
        if existing is None:
            db.add(CompanyRegistry(id=uuid.uuid4(), **item, detection_status="pending"))
            counts["inserted"] += 1
            continue
        changed = any((
            existing.careers_url != item["careers_url"],
            sorted(existing.source_tags or []) != item["source_tags"],
            existing.priority != item["priority"],
        ))
        if not changed:
            counts["skipped"] += 1
            continue
        if existing.careers_url != item["careers_url"]:
            existing.detection_status = "pending"
        existing.careers_url = item["careers_url"]
        existing.source_tags = item["source_tags"]
        existing.priority = item["priority"]
        counts["updated"] += 1
    db.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    args = parser.parse_args()
    with Path(args.csv_path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    db = SessionLocal()
    try:
        counts = import_rows(db, rows)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(" ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
