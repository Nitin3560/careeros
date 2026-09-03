from datetime import datetime
from typing import Optional

import httpx


def fetch_workable_jobs(company_slug: str) -> list[dict]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    raw_jobs = response.json().get("jobs", [])

    normalized = []
    for job in raw_jobs:
        shortcode = job.get("shortcode") or job.get("id")
        if not shortcode:
            continue

        normalized.append(
            {
                "external_id": f"workable_{shortcode}",
                "source": "workable",
                "company": company_slug,
                "title": job.get("title"),
                "location": _format_location(job.get("location")),
                "description_text": _extract_description(job),
                "application_url": job.get("url") or f"https://apply.workable.com/{company_slug}/j/{shortcode}/",
                "date_posted": _parse_date(job.get("published")),
                "retrieved_at": datetime.utcnow(),
            }
        )
    return normalized


def _format_location(location) -> str | None:
    if isinstance(location, str):
        return location or None
    if not isinstance(location, dict):
        return None
    parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    return ", ".join(part for part in parts if part) or None


def _extract_description(job: dict) -> str | None:
    fields = [
        job.get("description"),
        job.get("full_description"),
        job.get("requirements"),
        job.get("benefits"),
    ]
    return "\n\n".join(value for value in fields if value) or None


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
