#!/usr/bin/env python3
"""Block a noisy company, mark it second-hand, or clear its feed rule."""
import argparse
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def normalize_company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def main() -> None:
    from sqlalchemy import text
    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--action", required=True, choices=("block", "aggregator", "allow"))
    parser.add_argument("--reason", default="Manually reviewed feed company rule")
    args = parser.parse_args()
    key = normalize_company_key(args.company)
    if not key:
        parser.error("company must contain at least one letter or digit")
    db = SessionLocal()
    try:
        if args.action == "allow":
            db.execute(text("DELETE FROM job_feed_company_rules WHERE company_key=:key"), {"key": key})
        else:
            db.execute(text("""
                INSERT INTO job_feed_company_rules (company_key, company_name, rule, reason)
                VALUES (:key, :name, :rule, :reason)
                ON CONFLICT (company_key) DO UPDATE SET company_name=EXCLUDED.company_name,
                    rule=EXCLUDED.rule, reason=EXCLUDED.reason, updated_at=now()
            """), {"key": key, "name": args.company.strip(), "rule": args.action, "reason": args.reason})
        db.commit()
        print(f"company={args.company.strip()} action={args.action}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
