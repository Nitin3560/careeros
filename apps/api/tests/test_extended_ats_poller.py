import asyncio
import json
from pathlib import Path
import uuid

import httpx
import pytest

from app.ingestion.poller.fetcher import AsyncBoardFetcher
from app.ingestion.poller.config import PollerConfig
from app.ingestion.poller.normalization import normalize_job
from app.ingestion.poller.scheduler import PollScheduler
from app.ingestion.poller.types import BoardSpec, FetchResult


FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


def load(name):
    return json.loads((FIXTURES / name).read_text())


CASES = [
    ("phenom", "jobs.acme.com|acme", "phenom_page_1.json", "phenom_page_2.json", "phenom_PH1"),
    ("eightfold", "acme.eightfold.ai|acme", "eightfold_page_1.json", "eightfold_page_2.json", "eightfold_EF1"),
    ("oracle", "acme.fa.us2.oraclecloud.com|External", "oracle_page_1.json", "oracle_page_2.json", "oracle_OR1"),
    ("icims", "careers-acme.icims.com", "icims_page_1.json", "icims_page_2.json", "icims_IC1"),
]


def board(ats, slug):
    return BoardSpec(id=uuid.uuid4(), ats=ats, slug=slug)


@pytest.mark.parametrize("ats,slug,page1,page2,expected_id", CASES)
def test_tenant_adapter_paginates_complete_fixture_and_normalizes(ats, slug, page1, page2, expected_id):
    async def scenario():
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(200, request=request, json=load(page1 if calls == 1 else page2))

        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await fetcher.fetch_board(board(ats, slug))
        finally:
            await fetcher.client.aclose()
        return result, calls

    result, calls = asyncio.run(scenario())
    assert result.complete and len(result.jobs) == 2 and calls == 2
    normalized = normalize_job(ats, slug, result.jobs[0])
    assert normalized.external_id == expected_id
    if ats != "oracle":  # Oracle list rows intentionally defer job text.
        assert normalized.description_text
    assert normalized.raw_payload == result.jobs[0]


@pytest.mark.parametrize("ats,slug,page1,_page2,_expected_id", CASES)
def test_tenant_adapter_page_cap_is_incomplete(ats, slug, page1, _page2, _expected_id):
    async def scenario():
        def handler(request):
            return httpx.Response(200, request=request, json=load(page1))
        fetcher = AsyncBoardFetcher(concurrency=4, workday_max_pages=1)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await fetcher.fetch_board(board(ats, slug))
        finally:
            await fetcher.client.aclose()
    result = asyncio.run(scenario())
    assert not result.complete and "page cap" in result.error


def test_smartrecruiters_complete_list_and_deferred_detail_fixture():
    async def scenario():
        list_calls = 0

        def handler(request):
            nonlocal list_calls
            if "/postings/sr-1" in str(request.url):
                return httpx.Response(200, request=request, json=load("smartrecruiters_detail.json"))
            list_calls += 1
            fixture = "smartrecruiters_page_1.json" if list_calls == 1 else "smartrecruiters_page_2.json"
            return httpx.Response(200, request=request, json=load(fixture))
        selected = board("smartrecruiters", "acme")
        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await fetcher.fetch_board(selected)
            detail, ok = await fetcher.fetch_detail(selected, result.jobs[0])
        finally:
            await fetcher.client.aclose()
        return result, detail, ok
    result, detail, ok = asyncio.run(scenario())
    assert result.complete and len(result.jobs) == 2 and ok
    normalized = normalize_job("smartrecruiters", "acme", detail)
    assert normalized.external_id == "smartrecruiters_sr-1"
    assert "Requirements" in normalized.description_text


def test_workable_complete_list_and_deferred_detail_fixture():
    async def scenario():
        def handler(request):
            payload = load("workable_detail.json") if request.url.params.get("details") == "true" else load("workable_list.json")
            return httpx.Response(200, request=request, json=payload)
        selected = board("workable", "acme")
        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await fetcher.fetch_board(selected)
            detail, ok = await fetcher.fetch_detail(selected, result.jobs[0])
        finally:
            await fetcher.client.aclose()
        return result, detail, ok
    result, detail, ok = asyncio.run(scenario())
    assert result.complete and len(result.jobs) == 2 and ok
    assert "Build APIs" in normalize_job("workable", "acme", detail).description_text


def test_oracle_fetches_detail_before_normalizer_v2_text():
    async def scenario():
        def handler(request):
            return httpx.Response(200, request=request, json=load("oracle_detail.json"))
        selected = board("oracle", "acme.fa.us2.oraclecloud.com|External")
        fetcher = AsyncBoardFetcher(concurrency=4)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await fetcher.fetch_detail(selected, load("oracle_page_1.json")["items"][0])
        finally:
            await fetcher.client.aclose()
    detail, ok = asyncio.run(scenario())
    normalized = normalize_job("oracle", "acme.fa.us2.oraclecloud.com|External", detail)
    assert ok and "Build cloud services" in normalized.description_text


def test_each_tenant_has_independent_rate_controls():
    fetcher = AsyncBoardFetcher(concurrency=4)
    try:
        for ats in ("phenom", "eightfold", "oracle", "icims"):
            fetcher._ensure_tenant_host(f"{ats}:a.example")
            fetcher._ensure_tenant_host(f"{ats}:b.example")
            assert fetcher.host_sems[f"{ats}:a.example"] is not fetcher.host_sems[f"{ats}:b.example"]
            assert fetcher.buckets[f"{ats}:a.example"].rate == 2.0
    finally:
        asyncio.run(fetcher.client.aclose())


@pytest.mark.parametrize("ats,slug,raw,external", [
    ("smartrecruiters", "acme", {"id": "SR1", "name": "Engineer"}, "smartrecruiters_SR1"),
    ("workable", "acme", {"shortcode": "WK1", "title": "Engineer"}, "workable_WK1"),
    ("oracle", "host.oraclecloud.com|External", {"Id": "OR1", "Title": "Engineer"}, "oracle_OR1"),
])
def test_scheduler_fetches_details_for_new_jobs_only(ats, slug, raw, external):
    class Repo:
        async def board_job_state(self, _board_id):
            return {external: (False, None, False)}

    class Fetcher:
        def __init__(self):
            self.details = []

        async def fetch_board(self, selected):
            return FetchResult(board=selected, complete=True, status_code=200, jobs=[raw, {**raw, "id": "NEW", "Id": "NEW", "shortcode": "NEW"}])

        async def fetch_detail(self, _board, item):
            self.details.append(item)
            return {**item, "description": "<p>detail</p>", "ExternalJobDescription": "<p>detail</p>"}, True

    async def scenario():
        selected = board(ats, slug)
        fetcher = Fetcher()
        scheduler = PollScheduler(PollerConfig(database_url="postgresql+asyncpg://unused"), Repo())
        queue = asyncio.Queue()
        await scheduler._poll_one(selected, fetcher, queue)
        return fetcher, await queue.get()

    fetcher, write = asyncio.run(scenario())
    assert len(fetcher.details) == 1
    assert len(write.jobs) == 1
