from datetime import datetime

from sqlalchemy.orm import Session

from app import models

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

TERMINAL_STATUSES = {SUCCEEDED, FAILED}
ACTIVE_STATUSES = {QUEUED, RUNNING}


def get_active_background_job(
    db: Session,
    job_type: str,
    dedupe_key: str | None,
) -> models.BackgroundJob | None:
    if not dedupe_key:
        return None

    return (
        db.query(models.BackgroundJob)
        .filter(
            models.BackgroundJob.job_type == job_type,
            models.BackgroundJob.dedupe_key == dedupe_key,
            models.BackgroundJob.status.in_(ACTIVE_STATUSES),
        )
        .order_by(models.BackgroundJob.created_at.desc())
        .first()
    )


def create_background_job(
    db: Session,
    job_type: str,
    payload: dict | None = None,
    queue_job_id: str | None = None,
    dedupe_key: str | None = None,
) -> models.BackgroundJob:
    job = models.BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        queue_job_id=queue_job_id,
        dedupe_key=dedupe_key,
        status=QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_or_create_background_job(
    db: Session,
    job_type: str,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> tuple[models.BackgroundJob, bool]:
    existing = get_active_background_job(db, job_type, dedupe_key)
    if existing:
        return existing, False

    return create_background_job(db, job_type, payload, dedupe_key=dedupe_key), True


def set_queue_job_id(
    db: Session, job: models.BackgroundJob, queue_job_id: str
) -> models.BackgroundJob:
    job.queue_job_id = queue_job_id
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
