from sqlalchemy.orm import Session

from app import models


def save_jobs(db: Session, jobs: list[dict]) -> dict:
    """Save new jobs and skip existing external IDs."""
    inserted = 0
    skipped = 0

    for job_data in jobs:
        existing = (
            db.query(models.Job)
            .filter(models.Job.external_id == job_data["external_id"])
            .first()
        )

        if existing:
            skipped += 1
            continue

        db_job = models.Job(**job_data)
        db.add(db_job)
        inserted += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped}
