#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402


def rows_as_dicts(db, sql: str) -> list[dict]:
    return [dict(row) for row in db.execute(text(sql)).mappings().all()]


def build_report(db) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry": dict(db.execute(text("""
            SELECT count(*) AS total_companies,
              count(*) FILTER (WHERE detection_status='detected') AS detected,
              count(*) FILTER (WHERE detection_status='detected' AND detection_confidence='high') AS verified,
              count(*) FILTER (WHERE detection_confidence='low') AS low_confidence,
              count(*) FILTER (WHERE detection_status='not_found') AS not_found,
              count(*) FILTER (WHERE detection_status='error') AS error,
              count(*) FILTER (WHERE board_id IS NOT NULL) AS linked_to_board
            FROM company_registry
        """)).mappings().one()),
        "registry_by_ats": rows_as_dicts(db, """
            SELECT coalesce(detected_ats,'none') AS ats, detection_status,
                   count(*) AS companies
            FROM company_registry GROUP BY detected_ats, detection_status
            ORDER BY detected_ats, detection_status
        """),
        "unsupported_ats": rows_as_dicts(db, """
            SELECT detected_ats AS ats, count(*) AS companies
            FROM company_registry WHERE detection_status='unsupported'
            GROUP BY detected_ats ORDER BY companies DESC, detected_ats
        """),
        "boards": rows_as_dicts(db, """
            SELECT ats, status, tier, count(*) AS boards
            FROM ats_boards GROUP BY ats, status, tier ORDER BY ats, tier, status
        """),
        "active_jobs": rows_as_dicts(db, """
            SELECT source, count(*) AS active_jobs
            FROM jobs WHERE expired_at IS NULL GROUP BY source ORDER BY source
        """),
        "jobs_storage": dict(db.execute(text("""
            SELECT s.n_live_tup, s.n_dead_tup,
              round(100.0*s.n_dead_tup/greatest(s.n_live_tup+s.n_dead_tup,1),2) AS dead_ratio_pct,
              s.last_autovacuum,
              pg_relation_size(c.oid) AS table_bytes,
              pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
              pg_indexes_size(c.oid) AS index_bytes,
              pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
              coalesce(pg_total_relation_size(c.reltoastrelid),0) AS toast_bytes,
              pg_size_pretty(coalesce(pg_total_relation_size(c.reltoastrelid),0)) AS toast_size,
              pg_total_relation_size(c.oid) AS total_bytes,
              pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
            FROM pg_stat_user_tables s
            JOIN pg_class c ON c.relname=s.relname
            JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname=s.schemaname
            WHERE s.relname='jobs'
        """)).mappings().one_or_none() or {}),
        "expired_jobs": dict(db.execute(text("""
            SELECT count(*) FILTER (WHERE expired_at >= now()-interval '24 hours') AS last_24h,
                   count(*) FILTER (WHERE expired_at >= now()-interval '7 days') AS last_7d
            FROM jobs WHERE expired_at IS NOT NULL
        """)).mappings().one()),
        "new_jobs": rows_as_dicts(db, """
            SELECT source,
              count(*) FILTER (WHERE first_seen_at >= now()-interval '1 hour') AS last_1h,
              count(*) FILTER (WHERE first_seen_at >= now()-interval '24 hours') AS last_24h,
              count(*) FILTER (WHERE first_seen_at >= now()-interval '7 days') AS last_7d
            FROM jobs GROUP BY source ORDER BY source
        """),
        "description_quality": rows_as_dicts(db, """
            SELECT source, count(*) AS jobs,
              round(100.0*count(*) FILTER (WHERE coalesce(description_text,'')='')/greatest(count(*),1),2) AS pct_empty,
              round(100.0*count(*) FILTER (WHERE length(coalesce(description_text,''))<200)/greatest(count(*),1),2) AS pct_lt_200,
              round(100.0*count(*) FILTER (WHERE description_text LIKE '%## %')/greatest(count(*),1),2) AS pct_with_heading,
              round(100.0*count(*) FILTER (
                WHERE coalesce(description_text,'') ~ '<[^>]+>|&(?:[a-zA-Z]+|#[0-9]+);'
              )/greatest(count(*),1),2) AS pct_leftover_markup
            FROM jobs WHERE expired_at IS NULL GROUP BY source ORDER BY source
        """),
        "sweep_health": dict(db.execute(text("""
            SELECT p50_ms, p95_ms, boards_due, boards_polled,
                   round(100.0*boards_polled/greatest(boards_due,1),2) AS pct_polled_on_schedule,
                   started_at, finished_at
            FROM poll_runs WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 1
        """)).mappings().one_or_none() or {}),
        "schedule": dict(db.execute(text("""
            SELECT count(*) AS non_dead,
              count(*) FILTER (WHERE next_poll_at <= now()) AS due,
              count(*) FILTER (WHERE next_poll_at < now()-interval '20 minutes') AS lagged_over_20m,
              round(100.0*count(*) FILTER (WHERE next_poll_at >= now()-interval '20 minutes')/
                    greatest(count(*),1),2) AS pct_on_schedule
            FROM ats_boards WHERE status <> 'dead'
        """)).mappings().one()),
        "freshness": rows_as_dicts(db, """
            SELECT source,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM (first_seen_at-date_posted))/60) AS p50_minutes,
              percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM (first_seen_at-date_posted))/60) AS p95_minutes
            FROM jobs WHERE source IN ('ashby','lever') AND date_posted IS NOT NULL
            GROUP BY source ORDER BY source
        """),
        "top_companies": rows_as_dicts(db, """
            SELECT company, source, count(*) AS active_jobs
            FROM jobs WHERE expired_at IS NULL GROUP BY company, source
            ORDER BY active_jobs DESC LIMIT 50
        """),
    }


def print_report(report: dict) -> None:
    for section, value in report.items():
        print(f"\n## {section}")
        if isinstance(value, list):
            for row in value:
                print(json.dumps(row, default=str, sort_keys=True))
        else:
            print(json.dumps(value, default=str, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(ROOT / "reports" / "coverage_report.json"))
    args = parser.parse_args()
    db = SessionLocal()
    try:
        report = build_report(db)
    finally:
        db.close()
    print_report(report)
    output = Path(args.json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"\njson={output}")


if __name__ == "__main__":
    main()
