#!/usr/bin/env python3
"""Explain the classified-feed decision for a job UUID."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from app.classification.classifier import VERSION  # noqa: E402
from update_entry_jobs_readme import (  # noqa: E402
    DEFENSE_COMPANY_RE, TITLE_DEFENSE_RE, has_explicit_non_us_location,
    extract_entry_experience, has_required_experience_evidence, markdown_apply_link,
)


def explain(row, version: int = VERSION) -> list[str]:
    reasons = []
    checks = (
        (row["expired_at"] is None, "expired"),
        (row["classifier_version"] == version, "stale_or_unclassified"),
        (row["is_tech_title"] is True, "not_tech_title"),
        (row["is_senior_title"] is False, "senior_or_unknown_seniority"),
        (row["location_class"] in ("us", "unknown"), "non_us_or_unknown_location_class"),
        (row["sponsorship_block"] is not True, "sponsorship_restricted"),
        (row["employment_type"] == "full_time", "not_full_time"),
        (row["min_years_required"] is None or row["min_years_required"] <= 2, "over_2_years"),
        (row["application_url"] is not None, "missing_apply_url"),
        (bool(markdown_apply_link(row["application_url"])), "unsafe_or_invalid_apply_url"),
        (row["rule"] != "block", "company_blocklisted"),
        (row["company_is_verified"] is True, "company_name_unverified"),
        (row["first_seen_at"] is not None, "missing_first_seen_at"),
        (row["first_seen_at"] is None or (row["now"] - row["first_seen_at"]).total_seconds() <= 7 * 86400, "older_than_7_days"),
        (not has_explicit_non_us_location(row["location"]), "explicit_non_us_location_signal"),
        (not TITLE_DEFENSE_RE.search(row["title"] or "") and not DEFENSE_COMPANY_RE.search(row["display_company"] or ""), "defense_or_restricted_title_or_company"),
    )
    reasons.extend(reason for passed, reason in checks if not passed)
    return reasons


def main() -> None:
    from sqlalchemy import text
    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        row = db.execute(text("""
          SELECT now() AS now, j.id, j.company, coalesce(reg.company_name, nullif(b.company_display,''), b.company_name, j.company) AS display_company,
                 (reg.company_name IS NOT NULL OR nullif(b.company_display,'') IS NOT NULL OR nullif(b.company_name,'') IS NOT NULL) AS company_is_verified,
                 j.title, j.location, j.location_class, j.location_reason, j.is_tech_title,
                 j.is_senior_title, j.sponsorship_block, j.sponsorship_rule,
                 j.sponsorship_evidence, j.employment_type, j.min_years_required,
                 j.classifier_version, j.expired_at, j.first_seen_at, j.application_url, j.description_text,
                 r.rule, r.reason AS company_rule_reason
          FROM jobs j LEFT JOIN ats_boards b ON b.id=j.board_id
          LEFT JOIN LATERAL (SELECT company_name FROM company_registry cr
              WHERE cr.detection_status='detected' AND
                (cr.board_id=b.id OR lower(cr.company_name) IN
                  (lower(coalesce(b.company_display,'')), lower(coalesce(b.company_name,'')), lower(j.company)))
              ORDER BY (cr.board_id=b.id) DESC, cr.priority, cr.company_name LIMIT 1) reg ON true
          LEFT JOIN job_feed_company_rules r
            ON r.company_key=regexp_replace(lower(coalesce(nullif(b.company_display,''),reg.company_name,b.company_name,j.company)),'[^a-z0-9]','','g')
          WHERE j.id=CAST(:id AS uuid)
        """), {"id": args.job_id}).mappings().first()
        if not row:
            print(f"job_not_found: {args.job_id}")
            raise SystemExit(2)
        reasons = explain(row)
        if (row["min_years_required"] is not None or has_required_experience_evidence(row["description_text"])) and extract_entry_experience(row["description_text"]) is None:
            reasons.append("required_experience_not_safely_within_0_to_2_years")
        print(f"job_id: {row['id']}\ncompany: {row['display_company']}\nrole: {row['title']}\nlocation: {row['location'] or 'Unknown'} ({row['location_class'] or 'unclassified'}; {row['location_reason'] or 'no reason'})")
        print(f"classifier_version: {row['classifier_version']} (current={VERSION})\ntech: {row['is_tech_title']} senior: {row['is_senior_title']} employment: {row['employment_type']} min_years: {row['min_years_required']}")
        print(f"sponsorship_block: {row['sponsorship_block']} rule: {row['sponsorship_rule']} evidence: {row['sponsorship_evidence']}")
        print(f"company_rule: {row['rule']} ({row['company_rule_reason']})")
        print("feed_decision: INCLUDE" if not reasons else "feed_decision: EXCLUDE — " + ", ".join(reasons))
    finally:
        db.close()


if __name__ == "__main__":
    main()
