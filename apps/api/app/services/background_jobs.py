from datetime import datetime

from sqlalchemy.orm import Session

from app import models

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

TERMINAL_STATUSES = {SUCCEEDED, FAILED}


def create_background_job(
    db: Session,
    job_type: str,
    payload: dict | None = None,
    queue_job_id: str | None = None,
) -> models.BackgroundJob:
    job = models.BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        queue_job_id=queue_job_id,
        status=QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_running(db: Session, job: models.BackgroundJob) -> models.BackgroundJob:
    job.status = RUNNING
    job.attempts += 1
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def mark_job_succeeded(
    db: Session, job: models.BackgroundJob, result: dict | None = None
) -> models.BackgroundJob:
    job.status = SUCCEEDED
    job.result = result or {}
    job.error = None
    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(
    db: Session, job: models.BackgroundJob, error: str
) -> models.BackgroundJob:
    job.status = FAILED
    job.error = error
    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job
