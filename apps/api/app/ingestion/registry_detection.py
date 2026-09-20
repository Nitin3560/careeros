from __future__ import annotations

from dataclasses import dataclass, field
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
    endpoint_params: dict[str, str] = field(default_factory=dict)


SUPPORTED = (
    ("greenhouse", re.compile(r"(?:boards\.greenhouse\.io/embed/job_board|grnhse[^\"'<>\s]*)\?[^\"'<>\s]*\bfor=([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?!embed(?:/|$))([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([A-Za-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([A-Za-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:jobs|api)\.smartrecruiters\.com/(?:v1/companies/)?([A-Za-z0-9_-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/(?:api/v1/widget/accounts/)?([A-Za-z0-9_-]+)", re.I)),
)
WORKDAY = re.compile(
    r"(?P<host>(?P<tenant>[A-Za-z0-9-]+)\.wd\d+\.myworkdayjobs\.com)"
    r"/(?:[A-Za-z]{2}-[A-Za-z]{2}/)?(?P<site>[A-Za-z0-9_-]+)", re.I,
)
UNSUPPORTED = {
    "bamboohr": ("bamboohr.com",),
    "jazzhr": ("applytojob.com",), "recruitee": ("recruitee.com",),
    "breezy": ("breezy.hr",), "teamtailor": ("teamtailor.com",),
    "successfactors": ("successfactors.com",),
    "taleo": ("taleo.net",), "avature": ("avature.net",),
    "rippling": ("rippling.com",), "paylocity": ("paylocity.com",),
    "dover": ("dover.com",), "gem": ("gem.com",),
}

PHENOM = re.compile(r"https?://(?P<host>[^/]+)/(?:[^\"'\s]*)(?:phenom|jobapi)[^\"'\s]*", re.I)
EIGHTFOLD = re.compile(r"https?://(?P<host>[^/]*eightfold\.ai)/(?P<path>[^\"'\s]*)", re.I)
ORACLE = re.compile(r"https?://(?P<host>[^/]*oraclecloud\.com)/(?P<path>[^\"'\s]*)", re.I)
ICIMS = re.compile(r"https?://(?P<host>[^/]*icims\.com)/jobs(?:/search)?", re.I)


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
                slug = match.group(1)
                endpoint_params = {}
                if ats in {"smartrecruiters", "workable"}:
                    endpoint_params = {
                        "host": "api.smartrecruiters.com" if ats == "smartrecruiters" else "apply.workable.com",
                        "company_slug": slug,
                    }
                candidates.append((score, ATSMatch(
                    ats, slug, match.group(0), endpoint_params=endpoint_params,
                )))
        match = WORKDAY.search(value or "")
        if match:
            host, tenant, site = match.group("host", "tenant", "site")
            candidates.append((25 if value != markup else 30, ATSMatch(
                "workday", f"{host}|{tenant}|{site}", match.group(0),
                host.lower(), tenant, site,
            )))
        for ats, pattern in (("phenom", PHENOM), ("eightfold", EIGHTFOLD), ("oracle", ORACLE), ("icims", ICIMS)):
            endpoint = pattern.search(value or "")
            if endpoint:
                host = endpoint.group("host").lower()
                params = {"host": host, "endpoint": endpoint.group(0)}
                if ats == "phenom":
                    ref_num = re.search(r"refNum[=:]([A-Za-z0-9_-]+)", value or "", re.I)
                    tenant = ref_num.group(1) if ref_num else host.split(".")[0]
                    params["tenant"] = tenant
                    slug = f"{host}|{tenant}"
                elif ats == "eightfold":
                    tenant = host.split(".")[0]
                    params["tenant"] = tenant
                    slug = f"{host}|{tenant}"
                elif ats == "oracle":
                    site = re.search(r"siteNumber[=:]([A-Za-z0-9_-]+)", value or "", re.I)
                    params["site"] = site.group(1) if site else "External"
                    slug = f"{host}|{params['site']}"
                else:
                    slug = host
                candidates.append((25 if value != markup else 30, ATSMatch(
                    ats, slug, endpoint.group(0), endpoint_params=params,
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
    if match.ats == "smartrecruiters":
        response = await client.get(f"https://api.smartrecruiters.com/v1/companies/{match.slug}/postings", params={"limit": 1})
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("content"), list)
    if match.ats == "workable":
        response = await client.get(f"https://apply.workable.com/api/v1/widget/accounts/{match.slug}", params={"details": "true"})
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("jobs"), list)
    if match.ats == "phenom":
        host, tenant = match.slug.split("|", 1)
        response = await client.post(
            f"https://{host}/api/phenom/jobapi/searchjobs",
            json={"refNum": tenant, "pageSize": 1, "pageNo": 1},
        )
        payload = response.json() if response.is_success else None
        data = payload.get("data") if isinstance(payload, dict) else None
        return response.is_success and isinstance(data, dict) and isinstance(data.get("jobs"), list)
    if match.ats == "eightfold":
        host, tenant = match.slug.split("|", 1)
        response = await client.get(
            f"https://{host}/api/pcsx/search",
            params={"domain": tenant, "start": 0, "num": 1},
        )
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("positions"), list)
    if match.ats == "oracle":
        host, site = match.slug.split("|", 1)
        response = await client.get(
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
            params={"onlyData": "true", "limit": 1, "offset": 0,
                    "finder": f"findReqs;siteNumber={site}"},
        )
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("items"), list)
    if match.ats == "icims":
        response = await client.get(
            f"https://{match.slug}/jobs/search",
            params={"in_iframe": 1, "mode": "job", "pr": 1,
                    "searchRelation": "keyword_all", "format": "json"},
        )
        payload = response.json() if response.is_success else None
        return response.is_success and isinstance(payload, dict) and isinstance(payload.get("jobs"), list)
    return False
