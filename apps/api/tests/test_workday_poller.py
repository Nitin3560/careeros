import asyncio
import json
from pathlib import Path
import uuid

import httpx

from app.ingestion.poller.fetcher import AsyncBoardFetcher
from app.ingestion.poller.normalization import normalize_job
from app.ingestion.poller.types import BoardSpec

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def board():
    return BoardSpec(id=uuid.uuid4(), ats="workday", slug="acme.wd5.myworkdayjobs.com|acme|External")


def test_workday_paginates_fetches_detail_and_normalizes():
    async def scenario():
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, request=request, json=load("workday_detail.json"))
            offset = json.loads(request.content)["offset"]
            payload = load("workday_page_1.json") if offset == 0 else load("workday_page_2.json")
            return httpx.Response(200, request=request, json=payload)
        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await fetcher.fetch_board(board())
            detail, ok = await fetcher.fetch_workday_detail(board(), result.jobs[0])
        finally:
            await fetcher.client.aclose()
        normalized = normalize_job("workday", board().slug, detail)
        assert result.complete and len(result.jobs) == 2 and ok
        assert normalized.external_id == "workday_acme_R100"
        assert normalized.location == "Seattle, WA; Remote - US"
        assert normalized.date_posted is None
        assert normalized.application_url.endswith("/External/job/Seattle/Software-Engineer-I_R100")
        assert "## About the role" in normalized.description_text
    asyncio.run(scenario())


def test_workday_count_mismatch_and_page_cap_are_incomplete():
    async def scenario(max_pages):
        def handler(request):
            payload = {"total": 50, "jobPostings": [{"title": "SWE", "externalPath": f"/job/{json.loads(request.content)['offset']}"}]}
            return httpx.Response(200, request=request, json=payload)
        fetcher = AsyncBoardFetcher(concurrency=4, workday_max_pages=max_pages)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await fetcher.fetch_board(board())
        finally:
            await fetcher.client.aclose()
    capped = asyncio.run(scenario(1))
    assert not capped.complete and "page cap" in capped.error

    async def mismatch_scenario():
        def handler(request):
            return httpx.Response(200, request=request, json={"total": 3, "jobPostings": []})
        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await fetcher.fetch_board(board())
        finally:
            await fetcher.client.aclose()

    mismatched = asyncio.run(mismatch_scenario())
    assert not mismatched.complete and "count mismatch" in mismatched.error


def test_workday_rate_controls_are_scoped_per_host():
    fetcher = AsyncBoardFetcher(concurrency=4)
    try:
        fetcher._ensure_workday_host("workday:a.wd1.myworkdayjobs.com")
        fetcher._ensure_workday_host("workday:b.wd1.myworkdayjobs.com")
        assert fetcher.host_sems["workday:a.wd1.myworkdayjobs.com"] is not fetcher.host_sems["workday:b.wd1.myworkdayjobs.com"]
        assert fetcher.buckets["workday:a.wd1.myworkdayjobs.com"].rate == 2.0
        assert fetcher.workday_global_sem._value == 16
    finally:
        asyncio.run(fetcher.client.aclose())
