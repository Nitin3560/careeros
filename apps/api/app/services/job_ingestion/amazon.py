from datetime import datetime
from typing import Optional

import httpx


RESULT_LIMIT = 100
MAX_RESULTS = 2000


def fetch_amazon_jobs(query_slug: str = "software-development-engineer") -> list[dict]:
    query = query_slug.replace("-", " ").strip() or "software development engineer"
    normalized = []
    offset = 0
    total_hits = None

    while offset < MAX_RESULTS:
        response = httpx.get(
            "https://www.amazon.jobs/en/search.json",
            params={
                "base_query": query,
                "country": "USA",
                "loc_query": "United States",
                "offset": offset,
                "result_limit": RESULT_LIMIT,
                "sort": "relevant",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs") or []
        if total_hits is None:
            total_hits = int(data.get("hits") or 0)
        if not jobs:
            break

        for job in jobs:
            job_id = job.get("id_icims") or job.get("id")
            if not job_id:
                continue
            normalized.append(
                {
                    "external_id": f"amazon_{job_id}",
                    "source": "amazon",
                    "company": "amazon",
                    "title": job.get("title"),
                    "location": job.get("normalized_location") or job.get("location"),
                    "description_text": _description(job),
                    "application_url": job.get("url_next_step") or _job_url(job.get("job_path")),
                    "date_posted": _parse_date(job.get("posted_date")),
                    "retrieved_at": datetime.utcnow(),
                }
            )

        offset += len(jobs)
        if offset >= total_hits:
            break

    return normalized


def _description(job: dict) -> str:
    parts = [
        job.get("description"),
        job.get("basic_qualifications"),
        job.get("preferred_qualifications"),
    ]
    return "\n\n".join(part for part in parts if part)


def _job_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"https://www.amazon.jobs{path}"


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
