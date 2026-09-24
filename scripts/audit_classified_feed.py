#!/usr/bin/env python3
"""Report each classified-feed filter's impact and source freshness."""
import sys
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.classification.classifier import VERSION  # noqa: E402


COUNTS = """
WITH base AS (
  SELECT j.*, coalesce(reg.company_name, nullif(b.company_display,''), b.company_name, j.company) AS display_company,
         (reg.company_name IS NOT NULL OR nullif(b.company_display,'') IS NOT NULL OR nullif(b.company_name,'') IS NOT NULL) AS company_is_verified
  FROM jobs j LEFT JOIN ats_boards b ON b.id=j.board_id
  LEFT JOIN LATERAL (SELECT cr.company_name FROM company_registry cr
      WHERE cr.detection_status='detected' AND
        (cr.board_id=b.id OR lower(cr.company_name) IN
          (lower(coalesce(b.company_display,'')), lower(coalesce(b.company_name,'')), lower(j.company)))
      ORDER BY (cr.board_id=b.id) DESC, cr.priority, cr.company_name LIMIT 1) reg ON true
  WHERE j.expired_at IS NULL AND j.first_seen_at >= now() - interval '7 days'
), stages AS (
  SELECT count(*) AS active_recent,
    count(*) FILTER (WHERE classifier_version=:version) AS current_classifier,
    count(*) FILTER (WHERE classifier_version IS DISTINCT FROM :version) AS stale_or_unclassified,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS FALSE) AS non_tech,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE) AS tech,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE) AS non_senior_tech,
    count(*) FILTER (WHERE classifier_version=:version AND location_class='non_us') AS non_us_location,
    count(*) FILTER (WHERE classifier_version=:version AND location_class='unknown') AS unknown_location,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown')) AS us_or_unknown_location,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false) AS no_sponsorship_block,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false AND employment_type='full_time') AS full_time,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false AND employment_type='full_time' AND coalesce(min_years_required,0)>2) AS over_two_years,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false AND employment_type='full_time' AND coalesce(min_years_required,0)<=2) AS within_years_or_unstated,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false AND employment_type='full_time' AND coalesce(min_years_required,0)<=2 AND (application_url IS NULL OR application_url !~* '^https?://[^/ ]+')) AS unsafe_or_missing_apply_url,
    count(*) FILTER (WHERE classifier_version=:version AND is_tech_title IS TRUE AND is_senior_title IS FALSE AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false AND employment_type='full_time' AND coalesce(min_years_required,0)<=2 AND NOT company_is_verified) AS unresolved_company_name
  FROM base
), rule_counts AS (
  SELECT count(*) FILTER (WHERE r.rule='block') AS blocked_company_rows,
         count(*) FILTER (WHERE r.rule='aggregator') AS aggregator_rows
  FROM base j
  LEFT JOIN job_feed_company_rules r ON r.company_key=regexp_replace(lower(j.display_company),'[^a-z0-9]','','g')
  WHERE j.classifier_version=:version AND j.is_tech_title IS TRUE AND j.is_senior_title IS FALSE
    AND j.location_class IN ('us','unknown') AND coalesce(j.sponsorship_block,false)=false
    AND j.employment_type='full_time' AND coalesce(j.min_years_required,0)<=2 AND j.company_is_verified
)
SELECT * FROM stages CROSS JOIN rule_counts
"""


def main() -> None:
    db = SessionLocal()
    try:
        row = db.execute(text(COUNTS), {"version": VERSION}).mappings().one()
        print("7-day classified feed stages:")
        for key, value in row.items():
            print(f"  {key}: {value}")
        print("\nRecent source coverage (boards succeeded in last 2 hours):")
        rows = db.execute(text("""
            SELECT ats, count(*) AS boards,
                   count(*) FILTER (WHERE last_success_at >= now()-interval '2 hours') AS fresh,
                   count(*) FILTER (WHERE status='error') AS errors
            FROM ats_boards GROUP BY ats ORDER BY ats
        """)).mappings()
        for source in rows:
            print(f"  {source['ats']}: fresh={source['fresh']}/{source['boards']} errors={source['errors']}")
        daily = db.execute(text("""
            SELECT date_trunc('day', first_seen_at)::date AS day, count(*) AS classified_roles
            FROM jobs WHERE expired_at IS NULL AND classifier_version=:version
              AND first_seen_at >= now()-interval '7 days'
              AND is_tech_title IS TRUE AND is_senior_title IS FALSE
              AND location_class IN ('us','unknown') AND coalesce(sponsorship_block,false)=false
              AND employment_type='full_time' AND coalesce(min_years_required,0)<=2
            GROUP BY 1 ORDER BY 1 DESC
        """), {"version": VERSION}).mappings()
        print("\nDaily eligible volume before company/duplicate rules:")
        for item in daily:
            print(f"  {item['day']}: {item['classified_roles']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
