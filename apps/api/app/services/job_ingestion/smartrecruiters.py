from datetime import datetime
from typing import Optional

import httpx


def fetch_smartrecruiters_jobs(company_slug: str) -> list[dict]:
    jobs = []
    offset = 0
    limit = 100

    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings"
        response = httpx.get(url, params={"offset": offset, "limit": limit}, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        raw_jobs = payload.get("content", [])

        for job in raw_jobs:
            job_id = job.get("id") or job.get("uuid")
            if not job_id:
                continue

            jobs.append(
                {
                    "external_id": f"smartrecruiters_{job_id}",
                    "source": "smartrecruiters",
                    "company": company_slug,
                    "title": job.get("name") or job.get("title"),
                    "location": _format_location(job.get("location")),
                    "description_text": _extract_description(job),
                    "application_url": job.get("applyUrl") or job.get("ref"),
                    "date_posted": _parse_date(job.get("releasedDate")),
                    "retrieved_at": datetime.utcnow(),
                }
            )

        total = payload.get("totalFound", len(jobs))
        offset += len(raw_jobs)
        if not raw_jobs or offset >= total:
            break

    return jobs


def _format_location(location: dict | None) -> str | None:
    if not location:
        return None
    parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    value = ", ".join(part for part in parts if part)
    if location.get("remote"):
        return f"{value} Remote".strip()
    return value or None


def _extract_description(job: dict) -> str | None:
    job_ad = job.get("jobAd") or {}
    sections = job_ad.get("sections") or {}
    values = []
    for value in sections.values():
        if isinstance(value, dict):
            text = value.get("text") or value.get("value")
            if text:
                values.append(text)
        elif isinstance(value, str):
            values.append(value)
    return "\n\n".join(values) or job.get("description")


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
