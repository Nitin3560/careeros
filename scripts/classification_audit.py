#!/usr/bin/env python3
"""Report deterministic classification distributions and filter impact."""
import sys
from pathlib import Path
from sqlalchemy import text
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal

def main():
    db = SessionLocal()
    try:
        for row in db.execute(text("SELECT location_class, employment_type, count(*) FROM jobs WHERE classifier_version IS NOT NULL GROUP BY 1,2 ORDER BY 1,2")):
            print(f"location={row[0]} employment={row[1]} count={row[2]}")
        print("filter removals:")
        for name, clause in [("tech", "NOT is_tech_title"), ("senior", "is_senior_title"), ("location", "location_class NOT IN ('us','unknown')"), ("sponsorship", "sponsorship_block"), ("employment", "employment_type NOT IN ('full_time','unknown')")]:
            print(name, db.execute(text(f"SELECT count(*) FROM jobs WHERE classifier_version IS NOT NULL AND {clause}")).scalar_one())
        print("top sponsorship evidence:")
        for row in db.execute(text("SELECT sponsorship_rule,sponsorship_evidence,count(*) FROM jobs WHERE sponsorship_block AND sponsorship_evidence IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 30")):
            print(row[2], row[0], row[1])
    finally: db.close()
if __name__ == "__main__": main()
