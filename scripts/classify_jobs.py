#!/usr/bin/env python3
"""Batch, resumable deterministic classification of jobs."""
import argparse
import sys
from sqlalchemy import text
ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal
from app.classification import classify_job
from app.classification.classifier import VERSION

def main():
    p = argparse.ArgumentParser(); p.add_argument("--limit", type=int); p.add_argument("--sample", type=int); p.add_argument("--batch-size", type=int, default=1000)
    args = p.parse_args(); db = SessionLocal(); max_rows = args.sample or args.limit; processed = 0; last_id = None
    try:
        while max_rows is None or processed < max_rows:
            batch_limit = args.batch_size if max_rows is None else min(args.batch_size, max_rows - processed)
            rows = db.execute(text("""SELECT id,title,description_text,location FROM jobs
                WHERE classifier_version IS DISTINCT FROM :version AND (:after_id IS NULL OR id > :after_id)
                ORDER BY id LIMIT :batch_size"""), {"version": VERSION, "after_id": last_id, "batch_size": batch_limit}).mappings().all()
            if not rows: break
            for row in rows:
                values = classify_job(row["title"], row["description_text"], row["location"])
                db.execute(text("""UPDATE jobs SET title_normalized=:title_normalized,is_tech_title=:is_tech_title,tech_subfield=:tech_subfield,is_senior_title=:is_senior_title,seniority_level=:seniority_level,is_new_grad_title=:is_new_grad_title,employment_type=:employment_type,location_class=:location_class,location_reason=:location_reason,sponsorship_block=:sponsorship_block,sponsorship_evidence=:sponsorship_evidence,sponsorship_rule=:sponsorship_rule,min_years_required=:min_years_required,min_years_alternatives=CAST(:min_years_alternatives AS jsonb),years_source=:years_source,parse_tier=:parse_tier,exclusion_reasons=:exclusion_reasons,classifier_version=:classifier_version WHERE id=:id"""), {**values, "min_years_alternatives": __import__("json").dumps(values["min_years_alternatives"]), "exclusion_reasons": values["exclusion_reasons"], "id": row["id"]})
                last_id = row["id"]; processed += 1
            db.commit(); print(f"classified {processed}", flush=True)
        print(f"classified {processed}", flush=True)
    finally: db.close()
if __name__ == "__main__": main()
