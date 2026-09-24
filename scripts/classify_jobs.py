#!/usr/bin/env python3
"""Classify unclassified or stale jobs in resumable, independently committed batches."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys
import time
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.classification import classify_job  # noqa: E402
from app.classification.classifier import VERSION  # noqa: E402


SELECT_SQL = """
SELECT id, title, description_text, location
FROM jobs
WHERE classifier_version IS DISTINCT FROM :version
  {skip_clause}
ORDER BY first_seen_at, id
LIMIT :batch_size
FOR UPDATE SKIP LOCKED
"""

RETRY_SELECT_SQL = """
SELECT id, title, description_text, location
FROM jobs
WHERE classifier_version IS DISTINCT FROM :version
  AND id IN ({id_params})
ORDER BY first_seen_at, id
FOR UPDATE SKIP LOCKED
"""

UPDATE_SQL = text("""
UPDATE jobs SET
    title_normalized=:title_normalized,
    is_tech_title=:is_tech_title,
    tech_subfield=:tech_subfield,
    is_senior_title=:is_senior_title,
    seniority_level=:seniority_level,
    is_new_grad_title=:is_new_grad_title,
    employment_type=:employment_type,
    location_class=:location_class,
    location_reason=:location_reason,
    sponsorship_block=:sponsorship_block,
    sponsorship_evidence=:sponsorship_evidence,
    sponsorship_rule=:sponsorship_rule,
    min_years_required=:min_years_required,
    min_years_alternatives=CAST(:min_years_alternatives AS jsonb),
    years_source=:years_source,
    years_basis=:years_basis,
    parse_tier=:parse_tier,
    exclusion_reasons=:exclusion_reasons,
    classifier_version=:classifier_version
WHERE id=:id
""")


def is_deadlock_error(error: BaseException) -> bool:
    """Recognize PostgreSQL deadlocks through common SQLAlchemy driver wrappers."""
    current: Any = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if getattr(current, "sqlstate", None) == "40P01" or getattr(current, "pgcode", None) == "40P01":
            return True
        diag = getattr(current, "diag", None)
        if getattr(diag, "sqlstate", None) == "40P01":
            return True
        if "deadlock detected" in str(current).casefold():
            return True
        current = getattr(current, "orig", None) or getattr(current, "__cause__", None)
    return False


def _values_for(row: Any) -> dict[str, Any]:
    values = classify_job(row["title"], row["description_text"], row["location"])
    return {
        **values,
        "min_years_alternatives": json.dumps(values["min_years_alternatives"]),
        # PostgreSQL stores this field as text[], so bind a native list rather
        # than JSON text (which cannot be cast to jsonb and assigned to text[]).
        "exclusion_reasons": values["exclusion_reasons"],
        "classifier_version": VERSION,
        "id": row["id"],
    }


def _select_batch(db: Any, batch_size: int, version: int, skip_ids: set[str]) -> list[Any]:
    skip_clause = ""
    params: dict[str, Any] = {"version": version, "batch_size": batch_size}
    if skip_ids:
        ordered = sorted(skip_ids)
        placeholders = []
        for index, job_id in enumerate(ordered):
            name = f"skip_id_{index}"
            placeholders.append(f":{name}")
            params[name] = job_id
        skip_clause = f"AND id NOT IN ({', '.join(placeholders)})"
    query = text(SELECT_SQL.format(skip_clause=skip_clause))
    return list(db.execute(query, params).mappings().all())


def _select_retry_batch(db: Any, ids: list[Any], version: int) -> list[Any]:
    params = {"version": version}
    placeholders = []
    for index, job_id in enumerate(ids):
        name = f"retry_id_{index}"
        placeholders.append(f":{name}")
        params[name] = job_id
    query = text(RETRY_SELECT_SQL.format(id_params=", ".join(placeholders)))
    return list(db.execute(query, params).mappings().all())


def classify_pending_batches(
    session_factory: Callable[[], Any], *, batch_size: int = 500,
    limit: int | None = None, version: int = VERSION,
    max_deadlock_retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = print,
) -> dict[str, int]:
    """Process pending rows until empty, committing and locking one batch at a time."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    processed = batches = skipped_batches = 0
    retried_batch_keys: set[tuple[str, ...]] = set()
    skipped_ids: set[str] = set()

    while limit is None or processed < limit:
        db = session_factory()
        try:
            current_limit = batch_size if limit is None else min(batch_size, limit - processed)
            rows = _select_batch(db, current_limit, version, skipped_ids)
            if not rows:
                db.rollback()
                break
            batch_ids = [row["id"] for row in rows]
            batch_key = tuple(sorted(str(job_id) for job_id in batch_ids))
            values = [_values_for(row) for row in rows]
            # executemany applies updates in stable id order, matching the poller's lock order.
            values.sort(key=lambda item: str(item["id"]))
            try:
                db.execute(UPDATE_SQL, values)
                db.commit()
                processed += len(values)
                batches += 1
                report(f"classified batch={batches} rows={len(values)} total={processed}")
                continue
            except Exception as error:
                db.rollback()
                if not is_deadlock_error(error):
                    raise
                db.close()
                retry = 0
                while retry < max_deadlock_retries:
                    retried_batch_keys.add(batch_key)
                    sleep(min(0.5 * (2 ** retry), 8.0))
                    retry += 1
                    retry_db = session_factory()
                    try:
                        retry_rows = _select_retry_batch(retry_db, batch_ids, version)
                        if not retry_rows:
                            retry_db.rollback()
                            retry_db.close()
                            break
                        retry_values = [_values_for(row) for row in retry_rows]
                        retry_values.sort(key=lambda item: str(item["id"]))
                        retry_db.execute(UPDATE_SQL, retry_values)
                        retry_db.commit()
                        processed += len(retry_values)
                        batches += 1
                        report(f"classified batch={batches} rows={len(retry_values)} total={processed} after_deadlock_retries={retry}")
                        retry_db.close()
                        break
                    except Exception as retry_error:
                        retry_db.rollback()
                        retry_db.close()
                        if not is_deadlock_error(retry_error):
                            raise
                        if retry >= max_deadlock_retries:
                            skipped_batches += 1
                            skipped_ids.update(str(job_id) for job_id in batch_ids)
                            report(f"skipped batch ids={len(batch_ids)} after {retry} deadlock retries: {retry_error}")
                else:
                    # The first failure plus configured retries all deadlocked.
                    if not set(str(job_id) for job_id in batch_ids) <= skipped_ids:
                        skipped_batches += 1
                        skipped_ids.update(str(job_id) for job_id in batch_ids)
                        report(f"skipped batch ids={len(batch_ids)} after {max_deadlock_retries} deadlock retries")
        finally:
            db.close()

    return {
        "classified": processed,
        "batches": batches,
        "batches_retried": len(retried_batch_keys),
        "batches_skipped": skipped_batches,
    }


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--sample", type=_positive_int)
    parser.add_argument("--batch-size", type=_positive_int, default=500)
    parser.add_argument("--loop", action="store_true", help="repeat full classification passes continuously")
    parser.add_argument("--interval", type=_positive_int, default=60, help="seconds between passes when --loop is set")
    parser.add_argument("--deadlock-retries", type=_positive_int, default=3)
    args = parser.parse_args()
    max_rows = args.sample if args.sample is not None else args.limit

    from app.database import SessionLocal

    try:
        while True:
            summary = classify_pending_batches(
                SessionLocal, batch_size=args.batch_size, limit=max_rows,
                max_deadlock_retries=args.deadlock_retries,
            )
            print(
                f"pass complete: classified={summary['classified']} batches={summary['batches']} "
                f"batches_retried={summary['batches_retried']} batches_skipped={summary['batches_skipped']}",
                flush=True,
            )
            if not args.loop:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("classifier stopped", flush=True)


if __name__ == "__main__":
    main()
