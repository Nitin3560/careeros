from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import re

from sqlalchemy.orm import Session

from app import models


NEW_GRAD_PATTERN = re.compile(
    r"\b(new grad|new graduate|university grad|college grad|entry[- ]level|"
    r"early career|graduate software|software engineer i)\b",
    re.I,
)
SPONSORSHIP_POSITIVE_PATTERN = re.compile(
    r"\b(visa sponsorship|sponsor(?:ship)? available|h-?1b|opt|cpt)\b",
    re.I,
)
SPONSORSHIP_NEGATIVE_PATTERN = re.compile(
    r"\b(no sponsorship|does not sponsor|do not sponsor|unable to sponsor|"
    r"will not sponsor|without sponsorship)\b",
    re.I,
)
SOFTWARE_PATTERN = re.compile(
    r"\b(software|backend|frontend|full[- ]stack|platform|infrastructure|"
    r"machine learning|ai|data engineer|robotics|embedded|systems)\b",
    re.I,
)


@dataclass(frozen=True)
class CompanySignals:
    company: str
    open_job_count: int
    new_grad_job_count: int
    matching_job_count: int
    target_locations: list[str]
    explicit_sponsorship_status: str
    last_verified_at: datetime | None


def summarize_company_jobs(company: str, jobs: list[models.Job]) -> CompanySignals:
    descriptions = " ".join(
        f"{job.title or ''} {job.description_text or ''}" for job in jobs
    )
    status = infer_sponsorship_status(descriptions)
    locations = [
        location
        for location, _count in Counter(
            job.location for job in jobs if job.location
        ).most_common(8)
    ]
    verified_values = [
        value
        for job in jobs
        for value in (job.last_verified_at, job.last_seen_at, job.retrieved_at)
        if value is not None
    ]
    return CompanySignals(
        company=company,
        open_job_count=len(jobs),
        new_grad_job_count=sum(1 for job in jobs if is_new_grad_job(job)),
        matching_job_count=sum(1 for job in jobs if is_matching_job(job)),
        target_locations=locations,
        explicit_sponsorship_status=status,
        last_verified_at=max(verified_values) if verified_values else None,
    )


def infer_sponsorship_status(text: str) -> str:
    if SPONSORSHIP_NEGATIVE_PATTERN.search(text):
        return "no"
    if SPONSORSHIP_POSITIVE_PATTERN.search(text):
        return "yes"
    return "unknown"


def is_new_grad_job(job: models.Job) -> bool:
    text = f"{job.title or ''} {job.description_text or ''}"
    return bool(NEW_GRAD_PATTERN.search(text))


def is_matching_job(job: models.Job) -> bool:
    if job.eligible is False:
        return False
    text = f"{job.title or ''} {job.description_text or ''}"
    return bool(SOFTWARE_PATTERN.search(text))


def refresh_company_intelligence_from_jobs(db: Session) -> dict:
    jobs = (
        db.query(models.Job)
        .filter(models.Job.ingestion_status != "expired")
        .all()
    )
    by_company: dict[str, list[models.Job]] = {}
    for job in jobs:
        if job.company:
            by_company.setdefault(job.company, []).append(job)

    inserted = 0
    refreshed = 0
    for company, company_jobs in by_company.items():
        signals = summarize_company_jobs(company, company_jobs)
        record = (
            db.query(models.CompanyIntelligence)
            .filter(models.CompanyIntelligence.company == company)
            .first()
        )
        if record is None:
            record = models.CompanyIntelligence(company=company)
            db.add(record)
            inserted += 1
        else:
            refreshed += 1

        apply_job_signals(record, signals)

    db.commit()
    return {
        "companies": len(by_company),
        "inserted": inserted,
        "refreshed": refreshed,
    }


def apply_job_signals(
    record: models.CompanyIntelligence,
    signals: CompanySignals,
) -> None:
    record.open_job_count = signals.open_job_count
    record.new_grad_job_count = signals.new_grad_job_count
    record.matching_job_count = signals.matching_job_count
    record.target_locations = signals.target_locations
    record.explicit_sponsorship_status = signals.explicit_sponsorship_status
    record.last_verified_at = signals.last_verified_at
    record.updated_at = datetime.utcnow()


def opportunity_quality_score(record: models.CompanyIntelligence) -> int:
    score = 0
    score += min(record.matching_job_count * 8, 40)
    score += min(record.new_grad_job_count * 10, 20)
    score += sponsorship_score(record.explicit_sponsorship_status)
    score += warn_score(record.warn_severity)
    score += min(record.h1b_software_lca_1y, 20)
    return max(0, min(score, 100))


def sponsorship_score(status: str) -> int:
    if status == "yes":
        return 25
    if status == "no":
        return -40
    if status == "probable":
        return 15
    return 0


def warn_score(severity: str) -> int:
    return {
        "green": 10,
        "yellow": 0,
        "orange": -15,
        "red": -35,
    }.get(severity, 0)
