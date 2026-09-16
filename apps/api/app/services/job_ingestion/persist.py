from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app import models


def clean_text(value):
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def clean_job(job: dict) -> dict:
    return {key: clean_text(value) for key, value in job.items()}


TRACKING_QUERY_PARAMS = {
    "gh_jid",
    "gh_src",
    "iis",
    "iisn",
    "ref",
    "refid",
    "source",
    "trk",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None

    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip().rstrip("/") or None

    query = urlencode(
        [
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_PARAMS
        ],
        doseq=True,
    )
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def normalize_identity_part(value: str | None) -> str:
    if not value:
        return ""
    chars = [char.lower() if char.isalnum() else " " for char in value]
    return " ".join("".join(chars).split())


def build_identity_key(job: dict) -> str | None:
    canonical_url = job.get("canonical_url") or canonicalize_url(job.get("application_url"))
    if canonical_url:
        return f"url:{canonical_url}"

    company = normalize_identity_part(job.get("company"))
    title = normalize_identity_part(job.get("title"))
    location = normalize_identity_part(job.get("location"))
    if not company or not title:
        return None
    return f"role:{company}|{title}|{location}"


def prepare_job(job: dict, seen_at: datetime) -> dict:
    clean = clean_job(job)
    clean.setdefault("retrieved_at", seen_at)
    clean.setdefault("first_seen_at", seen_at)
    clean["last_seen_at"] = clean.get("last_seen_at") or clean["retrieved_at"] or seen_at
    clean.setdefault("last_verified_at", clean["last_seen_at"])
    clean.setdefault("ingestion_status", "new")
    clean.setdefault("seen_count", 1)
    clean["canonical_url"] = clean.get("canonical_url") or canonicalize_url(
        clean.get("application_url")
    )
    clean["identity_key"] = clean.get("identity_key") or build_identity_key(clean)
    if clean["ingestion_status"] != "expired":
        clean.setdefault("expired_at", None)
    return clean


def save_jobs(db: Session, jobs: list[dict]) -> dict:
    """Save jobs, refreshing lifecycle metadata for repeated external IDs."""
    seen_at = datetime.utcnow()
    unique_jobs = {}
    for job in jobs:
        clean = prepare_job(job, seen_at)
        unique_jobs.setdefault(clean["external_id"], clean)

    if not unique_jobs:
        return {"inserted": 0, "refreshed": 0, "skipped": 0}

    external_ids = list(unique_jobs)
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

    if db.bind and db.bind.dialect.name == "postgresql":
        insert_stmt = insert(models.Job).values(list(unique_jobs.values()))
        update_columns = {
            "source": insert_stmt.excluded.source,
            "company": insert_stmt.excluded.company,
            "title": insert_stmt.excluded.title,
            "location": insert_stmt.excluded.location,
            "description_text": insert_stmt.excluded.description_text,
            "application_url": insert_stmt.excluded.application_url,
            "canonical_url": insert_stmt.excluded.canonical_url,
            "identity_key": insert_stmt.excluded.identity_key,
            "date_posted": insert_stmt.excluded.date_posted,
            "retrieved_at": insert_stmt.excluded.retrieved_at,
            "last_seen_at": insert_stmt.excluded.last_seen_at,
            "last_verified_at": insert_stmt.excluded.last_verified_at,
            "expired_at": None,
            "ingestion_status": insert_stmt.excluded.ingestion_status,
            "seen_count": models.Job.seen_count + 1,
        }
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_=update_columns,
        )
        db.execute(stmt)
        db.commit()
        inserted = len(set(external_ids) - existing_ids)
        refreshed = len(existing_ids)
        return {
            "inserted": inserted,
            "refreshed": refreshed,
            "skipped": len(jobs) - len(unique_jobs),
        }

    for job_data in unique_jobs.values():
        external_id = job_data["external_id"]
        if external_id in existing_ids:
            existing = (
                db.query(models.Job)
                .filter(models.Job.external_id == external_id)
                .one()
            )
            for key, value in job_data.items():
                if key in {"id", "external_id", "first_seen_at", "seen_count"}:
                    continue
                setattr(existing, key, value)
            existing.expired_at = None
            existing.seen_count = (existing.seen_count or 0) + 1
            continue

        db.add(models.Job(**job_data))

    db.commit()
    inserted = len(unique_jobs) - len(existing_ids)
    refreshed = len(existing_ids)
    skipped = len(jobs) - len(unique_jobs)
    return {"inserted": inserted, "refreshed": refreshed, "skipped": skipped}
