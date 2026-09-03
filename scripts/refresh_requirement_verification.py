import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from extract_all_requirements import verify  # noqa: E402


def refresh_requirements(requirements: dict, description_text: str) -> int:
    changed = 0
    for req in requirements.get("hard_requirements", []):
        old_state = req.get("verification_state")
        old_note = req.get("verification_note")
        state, note = verify(req, description_text)
        req["verification_state"] = state
        req["verification_note"] = note
        if old_state != state or old_note != note:
            changed += 1
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    limit_sql = "LIMIT :limit" if args.limit else ""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                f"""
                SELECT jr.job_id, jr.requirements, j.description_text
                FROM job_requirements jr
                JOIN jobs j ON j.id = jr.job_id
                WHERE jr.status = 'ok'
                  AND j.description_text IS NOT NULL
                ORDER BY jr.extracted_at DESC
                {limit_sql}
                """
            ),
            {"limit": args.limit},
        ).fetchall()

        changed_jobs = 0
        changed_requirements = 0
        for row in rows:
            requirements = row.requirements
            changed = refresh_requirements(requirements, row.description_text)
            if not changed:
                continue
            changed_jobs += 1
            changed_requirements += changed
            db.execute(
                text(
                    """
                    UPDATE job_requirements
                    SET requirements = CAST(:requirements AS jsonb)
                    WHERE job_id = :job_id
                    """
                ),
                {"requirements": json.dumps(requirements), "job_id": row.job_id},
            )
        db.commit()
        print(f"jobs checked: {len(rows)}")
        print(f"jobs changed: {changed_jobs}")
        print(f"requirements changed: {changed_requirements}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
