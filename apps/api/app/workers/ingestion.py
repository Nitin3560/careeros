from app import models
from app.database import SessionLocal
from app.services.background_jobs import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from app.services.job_ingestion.bulk import ingest_active_greenhouse_targets


def run_bulk_greenhouse_ingestion(background_job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.id == background_job_id)
            .first()
        )
        if not job:
            raise ValueError("Background job not found")

        mark_job_running(db, job)
        result = ingest_active_greenhouse_targets(db)
        mark_job_succeeded(db, job, result)
        return result
    except Exception as exc:
        if "job" in locals() and job:
            mark_job_failed(db, job, str(exc))
        raise
    finally:
        db.close()
