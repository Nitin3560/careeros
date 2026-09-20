#!/usr/bin/env python3
"""Resumable description cleanup for existing jobs."""
import argparse
import hashlib
from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.ingestion.poller.normalization import NORMALIZER_VERSION, html_to_text, source_description_html  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    processed = 0
    while args.limit is None or processed < args.limit:
        size = min(args.batch_size, (args.limit - processed) if args.limit else args.batch_size)
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT id, source, title, location, description_html, raw_payload
                FROM jobs
                WHERE description_normalizer_version IS DISTINCT FROM :version
                ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED
            """), {"limit": size, "version": NORMALIZER_VERSION}).mappings().all()
            if not rows:
                db.rollback()
                break
            updates = []
            for row in rows:
                if row["description_html"]:
                    description_html = row["description_html"]
                    description_text = html_to_text(description_html)
                elif row["raw_payload"]:
                    description_html = source_description_html(row["source"], row["raw_payload"])
                    description_text = html_to_text(description_html)
                else:
                    description_html = ""
                    description_text = ""
                digest = hashlib.sha256(
                    "|".join((row["title"] or "", row["location"] or "", description_text)).encode()
                ).hexdigest()
                updates.append({
                    "id": row["id"], "html": description_html, "text": description_text,
                    "hash": digest, "status": "ok" if description_text else "failed",
                    "version": NORMALIZER_VERSION,
                })
            db.execute(text("""
                UPDATE jobs SET description_html=:html, description_text=:text,
                    content_hash=:hash, description_status=:status,
                    description_normalizer_version=:version WHERE id=:id
            """), updates)
            db.commit()
            processed += len(rows)
            print(f"descriptions_backfilled={processed}", flush=True)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


if __name__ == "__main__":
    main()
