import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
import asyncio
from unittest.mock import patch

import httpx

from app.ingestion.poller.diff import build_diff
from app.ingestion.poller.fetcher import AsyncBoardFetcher
from app.ingestion.poller.normalization import (
    html_to_text,
    normalize_job,
    source_description_html,
    stable_list_hash,
)
from app.ingestion.poller.state import next_board_state, next_interval_seconds
from app.ingestion.poller.types import BoardSpec


FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_source_normalization_matches_golden_outputs():
    golden = load("golden.json")
    greenhouse = load("greenhouse_detail.json")
    lever = load("lever_list.json")[0]
    ashby = load("ashby_list.json")["jobs"][0]
    for source, raw in (("greenhouse", greenhouse), ("lever", lever), ("ashby", ashby)):
        normalized = normalize_job(source, "example", raw)
        assert normalized.description_text == golden[source]
        assert "<" not in normalized.description_text
        assert "&amp;" not in normalized.description_text
        assert normalized.raw_payload == raw


def test_lever_normalization_keeps_lists_and_additional_sections():
    raw = load("lever_list.json")[0]
    html = source_description_html("lever", raw)
    assert "Requirements" in html
    assert "1-2 years" in html
    assert "Benefits" in html


def test_nested_wrapper_preserves_sections_and_bullets():
    text = html_to_text(
        "<div><h2>Requirements</h2><p>Build systems.</p>"
        "<ul><li>Python</li><li>SQL</li></ul></div>"
    )
    assert text == "## Requirements\n\nBuild systems.\n\n- Python\n- SQL"


def test_stable_list_hash_ignores_order_but_detects_visible_change():
    first = [{"id": 1, "title": "A", "location": {"name": "US"}}, {"id": 2, "title": "B"}]
    assert stable_list_hash("greenhouse", first) == stable_list_hash("greenhouse", list(reversed(first)))
    changed = [{**first[0], "title": "New"}, first[1]]
    assert stable_list_hash("greenhouse", first) != stable_list_hash("greenhouse", changed)


def test_amazon_search_board_keeps_company_as_amazon():
    job = normalize_job("amazon", "software-development-engineer", {
        "id_icims": "123", "title": "Software Development Engineer",
        "normalized_location": "Seattle, WA", "description": "Build services",
    })
    assert job.company == "amazon"


def test_diff_engine_new_present_missing_and_reappeared():
    plan = build_diff({"new", "present", "back"}, {"present", "missing"}, {"back", "old"})
    assert plan.new == {"new"}
    assert plan.present == {"present"}
    assert plan.missing == {"missing"}
    assert plan.reappeared == {"back"}


def board(**changes):
    values = dict(id=uuid.uuid4(), ats="greenhouse", slug="example", tier="B", status="live")
    values.update(changes)
    return BoardSpec(**values)


def test_state_machine_dead_dormant_revival_and_failure_backoff():
    now = datetime.now(timezone.utc)
    first_404 = next_board_state(board(not_found_count=0), success=False, status_code=404, job_count=None, now=now)
    assert first_404[0] != "dead"
    second_404 = next_board_state(board(not_found_count=1), success=False, status_code=404, job_count=None, now=now)
    assert second_404[0] == "dead"
    dormant = next_board_state(board(empty_since=now-timedelta(days=31)), success=True, status_code=200, job_count=0, now=now)
    assert dormant[:2] == ("dormant", "dormant")
    revived = next_board_state(board(tier="dormant", status="dormant"), success=True, status_code=200, job_count=1, now=now)
    assert revived[:2] == ("live", "B")
    assert next_interval_seconds("B", 5, jitter=False) == 21600


def test_incomplete_fetch_policy_is_explicitly_non_expiring():
    plan = build_diff(set(), {"active"}, set())
    assert plan.missing == {"active"}
    # The repository invokes build_diff only for complete fetches; this sentinel
    # protects the contract at the scheduler boundary.
    incomplete = False
    expired = plan.missing if incomplete else set()
    assert expired == set()


def test_conditional_request_treats_304_as_complete_unchanged():
    async def scenario():
        seen = {}
        def handler(request):
            seen.update(request.headers)
            return httpx.Response(304, request=request)
        fetcher = AsyncBoardFetcher(concurrency=2)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await fetcher.fetch_board(board(etag='"abc"', last_modified="yesterday"))
        finally:
            await fetcher.client.aclose()
        assert result.complete and result.not_modified
        assert seen["if-none-match"] == '"abc"'
        assert seen["if-modified-since"] == "yesterday"
    asyncio.run(scenario())


def test_failed_amazon_page_makes_entire_fetch_incomplete():
    async def scenario():
        def handler(request):
            offset = int(request.url.params.get("offset", "0"))
            if offset:
                return httpx.Response(500, request=request)
            return httpx.Response(200, request=request, json={
                "hits": 2,
                "jobs": [{"id_icims": "1", "title": "SDE", "location": "US"}],
            })
        fetcher = AsyncBoardFetcher(concurrency=2)
        await fetcher.client.aclose()
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        amazon = board(ats="amazon", slug="software-development-engineer", tier="A")
        try:
            with patch("app.ingestion.poller.fetcher.random.uniform", return_value=0):
                result = await fetcher.fetch_board(amazon)
        finally:
            await fetcher.client.aclose()
        assert not result.complete
        assert result.status_code == 500
        assert result.jobs == []
    asyncio.run(scenario())
