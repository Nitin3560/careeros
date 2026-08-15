from datetime import datetime
from typing import Optional

import httpx


def fetch_ashby_jobs(company_slug: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    raw_jobs = response.json().get("jobs", [])

    normalized = []
    for job in raw_jobs:
        normalized.append(
            {
                "external_id": f"ashby_{job['id']}",
                "source": "ashby",
                "company": company_slug,
                "title": job.get("title"),
                "location": _format_location(job.get("location")),
                "description_text": job.get("descriptionHtml") or job.get("descriptionPlain"),
                "application_url": job.get("jobUrl") or job.get("applyUrl"),
                "date_posted": _parse_date(job.get("publishedAt")),
                "retrieved_at": datetime.utcnow(),
            }
        )
    return normalized


def _format_location(value) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name") or value.get("location")
    return None


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
