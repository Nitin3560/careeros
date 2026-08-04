from datetime import datetime
from typing import Optional

import httpx


def fetch_greenhouse_jobs(company_slug: str) -> list[dict]:
    """
    Fetches live job postings from a company's public Greenhouse board
    and normalizes them into our standard job dict shape.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    raw_jobs = response.json().get("jobs", [])

    normalized = []
    for job in raw_jobs:
        normalized.append(
            {
                "external_id": f"greenhouse_{job['id']}",
                "source": "greenhouse",
                "company": company_slug,
                "title": job.get("title"),
                "location": (job.get("location") or {}).get("name"),
                "description_text": job.get("content"),
                "application_url": job.get("absolute_url"),
                "date_posted": _parse_date(job.get("updated_at")),
                "retrieved_at": datetime.utcnow(),
            }
        )
    return normalized


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
