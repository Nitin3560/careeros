import asyncio
from datetime import datetime, timezone
import os
import uuid

import pytest
from sqlalchemy import text

from app.ingestion.poller.config import PollerConfig
from app.ingestion.poller.normalization import normalize_job, stable_list_hash
from app.ingestion.poller.repository import PollRepository
from app.ingestion.poller.types import BoardSpec, BoardWrite, FetchResult


DATABASE_URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif("postgresql" not in DATABASE_URL, reason="requires PostgreSQL")


def async_url(value: str) -> str:
    return value.replace("postgresql://", "postgresql+asyncpg://", 1)


def test_postgres_board_transaction_preserves_first_seen_and_failed_fetch_never_expires():
    async def scenario():
        repo = PollRepository(PollerConfig(database_url=async_url(DATABASE_URL), expiry_enabled=True))
        board_id = uuid.uuid4()
        slug = f"poller-test-{board_id.hex[:8]}"
        board = BoardSpec(id=board_id, ats="ashby", slug=slug, tier="A", status="live")
        raw = {
            "id": "job-1", "title": "Software Engineer I", "location": "Remote - US",
            "jobUrl": "https://example.test/job-1", "publishedAt": "2026-09-19T00:00:00Z",
            "descriptionHtml": "<h2>Role</h2><p>First description</p>",
        }
        try:
            async with repo.sessions.begin() as session:
                await session.execute(text("""
                    INSERT INTO ats_boards
                        (id, ats, slug, status, tier, priority, poll_interval_seconds,
                         next_poll_at, consecutive_failures, not_found_count, created_at, updated_at)
                    VALUES (:id, 'ashby', :slug, 'live', 'A', 1, 900, now(), 0, 0, now(), now())
                """), {"id": board_id, "slug": slug})

            first = normalize_job("ashby", slug, raw)
            result = FetchResult(board=board, complete=True, status_code=200, jobs=[raw])
            await repo.write_board(BoardWrite(
                result=result, jobs=[first], fetched_ids={first.external_id},
                list_hash=stable_list_hash("ashby", [raw]),
            ))
            async with repo.sessions() as session:
                original = (await session.execute(text(
                    "SELECT first_seen_at FROM jobs WHERE board_id=:board_id"
                ), {"board_id": board_id})).scalar_one()

            updated_raw = {**raw, "descriptionHtml": "<h2>Role</h2><p>Changed description</p>"}
            updated = normalize_job("ashby", slug, updated_raw)
            await repo.write_board(BoardWrite(
                result=FetchResult(board=board, complete=True, status_code=200, jobs=[updated_raw]),
                jobs=[updated], fetched_ids={updated.external_id},
                list_hash=stable_list_hash("ashby", [updated_raw]),
            ))
            await repo.write_board(BoardWrite(
                result=FetchResult(board=board, complete=False, status_code=500, error="failed page 2")
            ))
            async with repo.sessions() as session:
                row = (await session.execute(text("""
                    SELECT first_seen_at, expired_at, description_text
                    FROM jobs WHERE board_id=:board_id
                """), {"board_id": board_id})).one()
            assert row.first_seen_at == original
            assert row.expired_at is None
            assert "Changed description" in row.description_text
        finally:
            async with repo.sessions.begin() as session:
                await session.execute(text("DELETE FROM jobs WHERE board_id=:id"), {"id": board_id})
                await session.execute(text("DELETE FROM ats_boards WHERE id=:id"), {"id": board_id})
            await repo.close()

    asyncio.run(scenario())


def test_postgres_missing_count_expires_on_second_complete_miss_only_when_enabled():
    async def scenario(expiry_enabled: bool):
        repo = PollRepository(PollerConfig(
            database_url=async_url(DATABASE_URL), expiry_enabled=expiry_enabled,
        ))
        board_id = uuid.uuid4()
        slug = f"poller-missing-test-{board_id.hex[:8]}"
        board = BoardSpec(id=board_id, ats="ashby", slug=slug, tier="A", status="live")
        raw = {
            "id": "missing-job", "title": "Software Engineer I", "location": "Remote - US",
            "jobUrl": "https://example.test/missing-job",
            "descriptionHtml": "<h2>Role</h2><p>Build systems.</p>",
        }
        job = normalize_job("ashby", slug, raw)
        empty = BoardWrite(
            result=FetchResult(board=board, complete=True, status_code=200, jobs=[]),
            fetched_ids=set(), list_hash=stable_list_hash("ashby", []),
        )
        try:
            async with repo.sessions.begin() as session:
                await session.execute(text("""
                    INSERT INTO ats_boards
                        (id, ats, slug, status, tier, priority, poll_interval_seconds,
                         next_poll_at, consecutive_failures, not_found_count, created_at, updated_at)
                    VALUES (:id, 'ashby', :slug, 'live', 'A', 1, 900, now(), 0, 0, now(), now())
                """), {"id": board_id, "slug": slug})
            await repo.write_board(BoardWrite(
                result=FetchResult(board=board, complete=True, status_code=200, jobs=[raw]),
                jobs=[job], fetched_ids={job.external_id},
                list_hash=stable_list_hash("ashby", [raw]),
            ))
            first_miss = await repo.write_board(empty)
            async with repo.sessions() as session:
                first = (await session.execute(text("""
                    SELECT missing_count, expired_at FROM jobs WHERE board_id=:board_id
                """), {"board_id": board_id})).one()
            second_miss = await repo.write_board(empty)
            async with repo.sessions() as session:
                second = (await session.execute(text("""
                    SELECT missing_count, expired_at, ingestion_status
                    FROM jobs WHERE board_id=:board_id
                """), {"board_id": board_id})).one()
            return first_miss, first, second_miss, second
        finally:
            async with repo.sessions.begin() as session:
                await session.execute(text("DELETE FROM jobs WHERE board_id=:id"), {"id": board_id})
                await session.execute(text("DELETE FROM ats_boards WHERE id=:id"), {"id": board_id})
            await repo.close()

    first_miss, first, second_miss, second = asyncio.run(scenario(True))
    assert first.missing_count == 1 and first.expired_at is None
    assert second.missing_count == 2 and second.expired_at is not None
    assert second.ingestion_status == "expired"
    assert first_miss.expired_jobs == 0 and second_miss.expired_jobs == 1

    _first_miss, first_disabled, _second_miss, second_disabled = asyncio.run(scenario(False))
    assert first_disabled.missing_count == 1 and first_disabled.expired_at is None
    assert second_disabled.missing_count == 2 and second_disabled.expired_at is None
