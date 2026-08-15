from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.services.job_ingestion.greenhouse import fetch_greenhouse_jobs
from app.services.job_ingestion.persist import save_jobs


def ingest_active_greenhouse_targets(db: Session) -> dict:
    targets = (
        db.query(models.CompanyTarget)
        .filter(
            models.CompanyTarget.source == "greenhouse",
            models.CompanyTarget.active.is_(True),
        )
        .all()
    )

    results = []
    for target in targets:
        try:
            jobs = fetch_greenhouse_jobs(target.slug)
            result = save_jobs(db, jobs)
            target.last_ingested_at = datetime.utcnow()
            target.active = True
            db.commit()
            results.append({"company": target.slug, **result})
        except Exception as exc:
            target.active = False
            db.commit()
            results.append({"company": target.slug, "error": str(exc)})

    succeeded = sum(1 for result in results if "error" not in result)
    failed = len(results) - succeeded
    total_inserted = sum(result.get("inserted", 0) for result in results)

    return {
        "companies_processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "total_jobs_inserted": total_inserted,
        "results": results,
    }
