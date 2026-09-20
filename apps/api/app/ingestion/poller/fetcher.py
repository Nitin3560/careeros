from __future__ import annotations

import asyncio
from collections import deque
from email.utils import parsedate_to_datetime
import json
import logging
import random
import time
from typing import Any

import httpx

from .types import BoardSpec, FetchResult


HOST_LIMITS = {"greenhouse": 16, "lever": 8, "ashby": 8, "amazon": 2}
HOST_RATES = {"greenhouse": 16.0, "lever": 8.0, "ashby": 8.0, "amazon": 2.0}
logger = logging.getLogger("careeros.poller")


class TokenBucket:
    def __init__(self, rate: float, capacity: float | None = None):
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = (1 - self.tokens) / self.rate
            await asyncio.sleep(delay)


class CircuitBreaker:
    def __init__(self):
        self.results: deque[bool] = deque(maxlen=50)
        self.open_until = 0.0

    async def wait(self) -> None:
        delay = self.open_until - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)

    def record(self, success: bool) -> bool:
        self.results.append(success)
        opened = False
        if len(self.results) == 50 and sum(not value for value in self.results) / 50 > 0.5:
            self.open_until = time.monotonic() + 120
            self.results.clear()
            opened = True
        return opened


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None


class AsyncBoardFetcher:
    def __init__(self, concurrency: int = 64, user_agent: str = "CareerOS-Collector/1.0", workday_max_pages: int = 150):
        self.global_sem = asyncio.Semaphore(concurrency)
        self.workday_global_sem = asyncio.Semaphore(16)
        self.workday_max_pages = workday_max_pages
        self.host_sems = {key: asyncio.Semaphore(value) for key, value in HOST_LIMITS.items()}
        self.buckets = {key: TokenBucket(HOST_RATES[key]) for key in HOST_LIMITS}
        self.breakers = {key: CircuitBreaker() for key in HOST_LIMITS}
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0),
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"},
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
        )

    async def __aenter__(self) -> "AsyncBoardFetcher":
        return self

    async def __aexit__(self, *_args) -> None:
        await self.client.aclose()

    def _ensure_workday_host(self, host: str) -> None:
        if host not in self.host_sems:
            self.host_sems[host] = asyncio.Semaphore(2)
            self.buckets[host] = TokenBucket(2.0)
            self.breakers[host] = CircuitBreaker()

    async def request(self, host: str, url: str, *, method: str = "GET", **kwargs) -> httpx.Response:
        if host.startswith("workday:"):
            self._ensure_workday_host(host)
        await self.breakers[host].wait()
        last_error: Exception | None = None
        for attempt in range(4):
            await self.buckets[host].acquire()
            try:
                async with self.global_sem, self.host_sems[host]:
                    if host.startswith("workday:"):
                        async with self.workday_global_sem:
                            response = await self.client.post(url, **kwargs) if method == "POST" else await self.client.get(url, **kwargs)
                    else:
                        response = await self.client.post(url, **kwargs) if method == "POST" else await self.client.get(url, **kwargs)
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable:
                    self._record_circuit(host, True)
                    return response
                self._record_circuit(host, False)
                if attempt == 3:
                    return response
                delay = _retry_after(response)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                self._record_circuit(host, False)
                if attempt == 3:
                    raise
                delay = None
            await asyncio.sleep(delay if delay is not None else random.uniform(0, 0.5 * (2**attempt)))
        if last_error:
            raise last_error
        raise RuntimeError("request retries exhausted")

    def _record_circuit(self, host: str, success: bool) -> None:
        if self.breakers[host].record(success):
            logger.warning(json.dumps({
                "event": "circuit_breaker_open", "host": host,
                "pause_seconds": 120, "time": time.time(),
            }))

    async def fetch_board(self, board: BoardSpec, *, amazon_pages: int | None = None) -> FetchResult:
        started = time.perf_counter()
        headers = {}
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified
        try:
            complete = True
            fetch_error = None
            if board.ats == "amazon":
                response, jobs, display = await self._fetch_amazon(board.slug, amazon_pages)
            elif board.ats == "workday":
                response, jobs, display, complete, fetch_error = await self._fetch_workday(board)
            else:
                response = await self.request(board.ats, self._list_url(board), headers=headers)
                if response.status_code == 304:
                    return FetchResult(
                        board=board, complete=True, status_code=304, not_modified=True,
                        etag=response.headers.get("etag") or board.etag,
                        last_modified=response.headers.get("last-modified") or board.last_modified,
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
                response.raise_for_status()
                payload = response.json()
                if board.ats == "lever":
                    if not isinstance(payload, list):
                        raise ValueError("Lever response is not a top-level array")
                    jobs = payload
                    display = None
                else:
                    if not isinstance(payload, dict):
                        raise ValueError(f"{board.ats} response is not an object")
                    jobs = payload.get("jobs", [])
                    display = payload.get("organizationName") or payload.get("name")
                if not isinstance(jobs, list):
                    raise ValueError("job list is not an array")
            return FetchResult(
                board=board,
                complete=complete,
                status_code=response.status_code,
                jobs=jobs,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                company_display=display,
                latency_ms=(time.perf_counter() - started) * 1000,
                error=fetch_error,
            )
        except httpx.HTTPStatusError as exc:
            return FetchResult(
                board=board, complete=False, status_code=exc.response.status_code,
                error=f"http {exc.response.status_code}",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            return FetchResult(
                board=board, complete=False, status_code=None,
                error=f"{type(exc).__name__}: {exc}"[:500],
                latency_ms=(time.perf_counter() - started) * 1000,
            )

    async def fetch_greenhouse_detail(self, board: BoardSpec, raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        try:
            response = await self.request(
                "greenhouse",
                f"https://boards-api.greenhouse.io/v1/boards/{board.slug}/jobs/{raw['id']}",
            )
            response.raise_for_status()
            return response.json(), True
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
            return raw, False

    async def fetch_workday_detail(self, board: BoardSpec, raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        try:
            host, tenant, site = board.slug.split("|", 2)
            path = raw["externalPath"]
            response = await self.request(
                f"workday:{host}", f"https://{host}/wday/cxs/{tenant}/{site}{path}",
            )
            response.raise_for_status()
            payload = response.json()
            detail = payload.get("jobPostingInfo", payload)
            if not isinstance(detail, dict):
                raise ValueError("Workday detail is not an object")
            return {**raw, **detail, "_workday_host": host, "_workday_tenant": tenant, "_workday_site": site}, True
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
            return raw, False

    @staticmethod
    def _list_url(board: BoardSpec) -> str:
        if board.ats == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{board.slug}/jobs"
        if board.ats == "lever":
            return f"https://api.lever.co/v0/postings/{board.slug}?mode=json"
        if board.ats == "ashby":
            return f"https://api.ashbyhq.com/posting-api/job-board/{board.slug}"
        raise ValueError(f"unsupported ATS: {board.ats}")

    async def _fetch_amazon(self, slug: str, page_limit: int | None) -> tuple[httpx.Response, list[dict], str]:
        query = slug.replace("-", " ")
        jobs: list[dict] = []
        offset = 0
        pages = 0
        total = None
        last_response: httpx.Response | None = None
        while offset < 2000:
            last_response = await self.request(
                "amazon",
                "https://www.amazon.jobs/en/search.json",
                params={
                    "base_query": query,
                    "country": "USA",
                    "loc_query": "United States",
                    "offset": offset,
                    "result_limit": 100,
                    "sort": "recent",
                },
                headers={"Accept-Encoding": "identity"},
            )
            last_response.raise_for_status()
            payload = last_response.json()
            if not isinstance(payload, dict):
                raise ValueError("Amazon response is not an object")
            page = payload.get("jobs") or []
            if not isinstance(page, list):
                raise ValueError("Amazon jobs page is not an array")
            if total is None:
                total = int(payload.get("hits") or 0)
            jobs.extend(page)
            pages += 1
            if not page or offset + len(page) >= total or (page_limit and pages >= page_limit):
                break
            offset += len(page)
        if last_response is None:
            raise ValueError("Amazon returned no response")
        return last_response, jobs, "Amazon"

    async def _fetch_workday(self, board: BoardSpec) -> tuple[httpx.Response, list[dict], str, bool, str | None]:
        host, tenant, site = board.slug.split("|", 2)
        url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        jobs: list[dict] = []
        offset = 0
        total: int | None = None
        last_response: httpx.Response | None = None
        hit_cap = False
        for _page in range(self.workday_max_pages):
            last_response = await self.request(
                f"workday:{host}", url, method="POST",
                json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""},
            )
            last_response.raise_for_status()
            payload = last_response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("jobPostings"), list):
                raise ValueError("Workday response has no jobPostings array")
            page = payload["jobPostings"]
            if total is None:
                total = int(payload.get("total") or 0)
            for raw in page:
                jobs.append({**raw, "_workday_host": host, "_workday_tenant": tenant, "_workday_site": site})
            if not page or len(jobs) >= total:
                break
            offset += len(page)
        else:
            hit_cap = True
        if last_response is None:
            raise ValueError("Workday returned no response")
        mismatch = total is None or len(jobs) != total
        complete = not hit_cap and not mismatch
        error = None
        if hit_cap:
            error = f"Workday page cap reached ({self.workday_max_pages})"
        elif mismatch:
            error = f"Workday count mismatch collected={len(jobs)} total={total}"
        return last_response, jobs, tenant, complete, error
