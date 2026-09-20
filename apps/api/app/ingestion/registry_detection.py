from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

import httpx
from lxml import html as lxml_html


@dataclass(frozen=True)
class ATSMatch:
    ats: str
    slug: str | None
    evidence: str
    workday_host: str | None = None
    workday_tenant: str | None = None
    workday_site: str | None = None
    supported: bool = True


SUPPORTED = (
    ("greenhouse", re.compile(r"(?:boards\.greenhouse\.io/embed/job_board|grnhse[^\"'<>\s]*)\?[^\"'<>\s]*\bfor=([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?!embed(?:/|$))([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([A-Za-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([A-Za-z0-9_-]+)", re.I)),
)
WORKDAY = re.compile(
    r"(?P<host>(?P<tenant>[A-Za-z0-9-]+)\.wd\d+\.myworkdayjobs\.com)"
    r"/(?:[A-Za-z]{2}-[A-Za-z]{2}/)?(?P<site>[A-Za-z0-9_-]+)", re.I,
)
UNSUPPORTED = {
    "smartrecruiters": ("smartrecruiters.com",), "icims": ("icims.com",),
    "workable": ("workable.com",), "bamboohr": ("bamboohr.com",),
    "jazzhr": ("applytojob.com",), "recruitee": ("recruitee.com",),
    "breezy": ("breezy.hr",), "teamtailor": ("teamtailor.com",),
    "eightfold": ("eightfold.ai",), "phenom": ("phenom.com", "phenompeople.com"),
    "successfactors": ("successfactors.com",),
    "oracle": ("oraclecloud.com", "candidateexperience", "hcmui"),
    "taleo": ("taleo.net",), "avature": ("avature.net",),
    "rippling": ("rippling.com",), "paylocity": ("paylocity.com",),
    "dover": ("dover.com",), "gem": ("gem.com",),
}


def html_urls(markup: str) -> list[str]:
    try:
        root = lxml_html.fromstring(markup or "<html></html>")
    except (ValueError, TypeError):
        return []
    values = []
    for node in root.xpath("//*[@href or @src]"):
        values.extend(value for value in (node.get("href"), node.get("src")) if value)
    return values


def find_ats(redirect_urls: Iterable[str], final_url: str, markup: str, network_urls: Iterable[str] = ()) -> ATSMatch | None:
    urls = [*redirect_urls, final_url, *html_urls(markup), *network_urls]
    searchable = [*urls, markup]
    candidates: list[tuple[int, ATSMatch]] = []
    for value in searchable:
        for ats, pattern in SUPPORTED:
            match = pattern.search(value or "")
            if match:
                score = 30 if value == markup else 20
                if "api." in match.group(0) or "grnhse" in match.group(0).lower() or "embed/job_board" in match.group(0).lower():
                    score += 5
                candidates.append((score, ATSMatch(ats, match.group(1), match.group(0))))
        match = WORKDAY.search(value or "")
        if match:
            host, tenant, site = match.group("host", "tenant", "site")
            candidates.append((25 if value != markup else 30, ATSMatch(
                "workday", f"{host}|{tenant}|{site}", match.group(0),
                host.lower(), tenant, site,
            )))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    combined = "\n".join(searchable).lower()
    for ats, needles in UNSUPPORTED.items():
        evidence = next((needle for needle in needles if needle in combined), None)
        if evidence:
            return ATSMatch(ats, None, evidence, supported=False)
    return None


async def verify_match(client: httpx.AsyncClient, match: ATSMatch) -> bool:
    if match.ats == "greenhouse":
        response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{match.slug}/jobs")
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("jobs"), list)
    if match.ats == "lever":
        response = await client.get(f"https://api.lever.co/v0/postings/{match.slug}?mode=json")
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, list)
    if match.ats == "ashby":
        response = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{match.slug}")
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("jobs"), list)
    if match.ats == "workday":
        response = await client.post(
            f"https://{match.workday_host}/wday/cxs/{match.workday_tenant}/{match.workday_site}/jobs",
            json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
        )
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("jobPostings"), list)
    return False
