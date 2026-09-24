#!/usr/bin/env python3
"""Append an outside posting to the miss log or explain logged misses."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))


def normalize_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isascii() and char.isalnum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company")
    parser.add_argument("--title")
    parser.add_argument("--url")
    parser.add_argument("--reason")
    parser.add_argument("--summary", action="store_true", help="show coverage or classification gap for each logged miss")
    args = parser.parse_args()
    if not args.summary:
        missing = [option for option in ("company", "title", "reason") if not getattr(args, option)]
        if missing:
            parser.error("logging requires --company, --title, and --reason")
        if not args.company.strip() or not args.title.strip() or not args.reason.strip():
            parser.error("company, title, and reason must contain non-whitespace text")

    from sqlalchemy import text
    from app.database import SessionLocal
    from generate_feed import filter_reasons

    db = SessionLocal()
    try:
        if not args.summary:
            result = db.execute(text("""
                INSERT INTO misses (company, title, url, reason)
                VALUES (:company, :title, :url, :reason) RETURNING id, created_at
            """), {
                "company": " ".join(args.company.split()),
                "title": " ".join(args.title.split()),
                "url": args.url,
                "reason": args.reason.strip(),
            }).one()
            db.commit()
            print(f"miss_id={result.id} logged_at={result.created_at}")
            return

        misses = db.execute(text("SELECT id, company, title, url, reason, created_at FROM misses ORDER BY created_at DESC, id DESC")).mappings().all()
        now = datetime.now(timezone.utc)
        for miss in misses:
            url_clause = " OR j.application_url=:url OR j.canonical_url=:url" if miss["url"] else ""
            params = {
                "company": normalize_key(miss["company"]),
                "title": normalize_key(miss["title"]),
                "url": miss["url"],
            }
            match_sql = """
                SELECT j.id, j.company, j.title, j.location, j.location_class,
                       j.expired_at, j.first_seen_at, j.is_tech_title, j.is_senior_title,
                       j.sponsorship_block, j.employment_type,
                       EXISTS (SELECT 1 FROM company_blocklist cb WHERE cb.slug=j.company) AS blocklisted
                FROM jobs j
                LEFT JOIN ats_boards b ON b.id=j.board_id
                LEFT JOIN LATERAL (
                    SELECT cr.company_name FROM company_registry cr WHERE cr.board_id=j.board_id
                    ORDER BY (cr.detection_status='detected') DESC, cr.priority, cr.company_name LIMIT 1
                ) reg ON TRUE
                WHERE (
                    (regexp_replace(lower(coalesce(nullif(b.company_display,''), reg.company_name, b.company_name, j.company)), '[^a-z0-9]', '', 'g')=:company
                     AND regexp_replace(lower(j.title), '[^a-z0-9]', '', 'g')=:title)
                    {url_clause}
                )
                ORDER BY j.first_seen_at DESC NULLS LAST
            """.format(url_clause=url_clause)
            matches = db.execute(text(match_sql), params).mappings().all()
            context = f"miss_id={miss['id']} {miss['company']} | {miss['title']} | logged={miss['created_at']} | reason={miss['reason']}"
            if not matches:
                print(f"COVERAGE GAP | {context} | no matching job row found")
                continue
            row = dict(matches[0])
            dropped = filter_reasons(row, now=now)
            if dropped:
                print(f"CLASSIFICATION GAP | {context} | job_id={row['id']} dropped_by={', '.join(dropped)}")
            else:
                print(f"IN FEED CANDIDATES | {context} | job_id={row['id']} (may be collapsed with another location)")
        if not misses:
            print("No logged misses.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
