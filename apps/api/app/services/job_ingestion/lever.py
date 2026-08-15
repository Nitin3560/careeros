from datetime import datetime
from typing import Optional

import httpx


def fetch_lever_jobs(company_slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    raw_jobs = response.json()

    normalized = []
    for job in raw_jobs:
        normalized.append(
            {
                "external_id": f"lever_{job['id']}",
                "source": "lever",
                "company": company_slug,
                "title": job.get("text"),
                "location": (job.get("categories") or {}).get("location"),
                "description_text": job.get("descriptionPlain") or job.get("description"),
                "application_url": job.get("hostedUrl"),
                "date_posted": _parse_timestamp(job.get("createdAt")),
                "retrieved_at": datetime.utcnow(),
            }
        )
    return normalized


def _parse_timestamp(value: Optional[int]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000)
    except (TypeError, ValueError, OSError):
        return None
