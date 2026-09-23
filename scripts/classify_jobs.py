#!/usr/bin/env python3
"""Batch, resumable deterministic classification of jobs."""
import argparse
import sys
from sqlalchemy import text
ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal
from app.classification import classify_job

def main():
    p = argparse.ArgumentParser(); p.add_argument("--limit", type=int); p.add_argument("--sample", type=int)
    args = p.parse_args(); db = SessionLocal()
    try:
        limit = args.sample or args.limit
        sql = "SELECT id,title,description_text,location FROM jobs WHERE classifier_version IS DISTINCT FROM 1 ORDER BY id"
        if limit: sql += f" LIMIT {int(limit)}"
        rows = db.execute(text(sql)).mappings().all()
        for i, row in enumerate(rows, 1):
            values = classify_job(row["title"], row["description_text"], row["location"])
            values["id"] = row["id"]
            db.execute(text("""UPDATE jobs SET title_normalized=:title_normalized,is_tech_title=:is_tech_title,tech_subfield=:tech_subfield,is_senior_title=:is_senior_title,seniority_level=:seniority_level,is_new_grad_title=:is_new_grad_title,employment_type=:employment_type,location_class=:location_class,location_reason=:location_reason,sponsorship_block=:sponsorship_block,sponsorship_evidence=:sponsorship_evidence,sponsorship_rule=:sponsorship_rule,min_years_required=:min_years_required,min_years_alternatives=CAST(:min_years_alternatives AS jsonb),years_source=:years_source,parse_tier=:parse_tier,exclusion_reasons=:exclusion_reasons,classifier_version=:classifier_version WHERE id=:id"""), {**values, "min_years_alternatives": __import__("json").dumps(values["min_years_alternatives"]), "exclusion_reasons": values["exclusion_reasons"]})
            if i % 1000 == 0: db.commit(); print(f"classified {i}/{len(rows)}", flush=True)
        db.commit(); print(f"classified {len(rows)}", flush=True)
    finally: db.close()
if __name__ == "__main__": main()
