from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app import models


def save_jobs(db: Session, jobs: list[dict]) -> dict:
    """Save new jobs and skip existing external IDs."""
    unique_jobs = {}
    for job in jobs:
        unique_jobs.setdefault(job["external_id"], job)

    external_ids = list(unique_jobs)
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = (
            insert(models.Job)
            .values(list(unique_jobs.values()))
            .on_conflict_do_nothing(index_elements=["external_id"])
        )
        result = db.execute(stmt)
        db.commit()
        inserted = result.rowcount or 0
        return {"inserted": inserted, "skipped": len(jobs) - inserted}

    existing_ids = (
        {
            row[0]
            for row in db.query(models.Job.external_id)
            .filter(models.Job.external_id.in_(external_ids))
            .all()
        }
        if external_ids
        else set()
    )

    for job_data in unique_jobs.values():
        if job_data["external_id"] in existing_ids:
            continue

        db.add(models.Job(**job_data))

    db.commit()
    inserted = len(unique_jobs) - len(existing_ids)
    skipped = len(jobs) - inserted
    return {"inserted": inserted, "skipped": skipped}
