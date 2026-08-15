from app import models
from app.database import SessionLocal
from app.services.background_jobs import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from app.services.job_matching import get_or_create_matches


def run_match_refresh(background_job_id: str) -> dict:
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
        user_id = job.payload["user_id"]
        offset = int(job.payload.get("offset", 0))
        limit = int(job.payload.get("limit", 10))

        profile = (
            db.query(models.CandidateProfile)
            .filter(models.CandidateProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ValueError("Candidate profile not found")

        results = get_or_create_matches(
            db,
            user_id,
            profile,
            offset=offset,
            page_size=limit,
        )
        result = {
            "offset": offset,
            "limit": limit,
            "count": len(results),
            "has_more": len(results) == limit,
        }
        mark_job_succeeded(db, job, result)
        return result
    except Exception as exc:
        if "job" in locals() and job:
            mark_job_failed(db, job, str(exc))
        raise
    finally:
        db.close()
