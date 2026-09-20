#!/usr/bin/env python3
"""Resumable description cleanup for existing jobs."""
import argparse
import hashlib
from pathlib import Path
import sys
import time

from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.ingestion.poller.normalization import NORMALIZER_VERSION, html_to_text, source_description_html  # noqa: E402


def build_updates(rows):
    """Split expensive content rewrites from cheap version-only progress updates."""
    changed = []
    unchanged_ids = []
    for row in rows:
        raw_html = source_description_html(row["source"], row["raw_payload"] or {})
        description_html = raw_html or row["description_html"] or ""
        description_text = html_to_text(description_html)
        digest = hashlib.sha256(
            "|".join((row["title"] or "", row["location"] or "", description_text)).encode()
        ).hexdigest()
        if digest == row["content_hash"]:
            unchanged_ids.append(row["id"])
            continue
        changed.append({
            "id": row["id"], "text": description_text, "hash": digest,
            "status": "ok" if description_text else "failed",
            "version": NORMALIZER_VERSION,
        })
    return changed, unchanged_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--sleep-between-batches", type=float, default=1.0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    processed = 0
    while args.limit is None or processed < args.limit:
        size = min(args.batch_size, (args.limit - processed) if args.limit else args.batch_size)
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT id, source, title, location, description_html, raw_payload, content_hash
                FROM jobs
                WHERE description_normalizer_version IS DISTINCT FROM :version
                ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED
            """), {"limit": size, "version": NORMALIZER_VERSION}).mappings().all()
            if not rows:
                db.rollback()
                break
            updates, unchanged_ids = build_updates(rows)
            if updates:
                db.execute(text("""
                UPDATE jobs SET description_text=:text,
                    content_hash=:hash, description_status=:status,
                    description_normalizer_version=:version WHERE id=:id
                """), updates)
            if unchanged_ids:
                db.execute(
                    text("""
                        UPDATE jobs SET description_normalizer_version=:version
                        WHERE id IN :ids
                    """).bindparams(bindparam("ids", expanding=True)),
                    {"version": NORMALIZER_VERSION, "ids": unchanged_ids},
                )
            db.commit()
            processed += len(rows)
            print(
                f"descriptions_backfilled={processed} content_changed={len(updates)} "
                f"metadata_only={len(unchanged_ids)}",
                flush=True,
            )
            if args.sleep_between_batches > 0:
                time.sleep(args.sleep_between_batches)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


if __name__ == "__main__":
    main()
