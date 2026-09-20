#!/usr/bin/env python3
"""Resumably hydrate legacy Greenhouse jobs without slowing normal sweeps."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.ingestion.poller import PollerConfig  # noqa: E402
from app.ingestion.poller.fetcher import AsyncBoardFetcher  # noqa: E402
from app.ingestion.poller.normalization import normalize_job  # noqa: E402
from app.ingestion.poller.repository import PollRepository  # noqa: E402
from app.ingestion.poller.types import BoardSpec  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=5.0, help="maximum detail requests per second")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


async def claim_batch(repo: PollRepository, batch_size: int) -> list[dict]:
    async with repo.sessions() as session:
        rows = (await session.execute(text("""
            SELECT j.id AS job_id, j.external_id, b.id AS board_id, b.slug
            FROM jobs j JOIN ats_boards b ON b.id=j.board_id
            WHERE j.source='greenhouse' AND j.raw_payload IS NULL AND j.expired_at IS NULL
            ORDER BY j.id LIMIT :limit
        """), {"limit": batch_size})).mappings().all()
    return [dict(row) for row in rows]


async def save_detail(repo: PollRepository, job_id, normalized) -> None:
    async with repo.sessions.begin() as session:
        await session.execute(text("""
            UPDATE jobs SET description_text=:description_text,
                description_html=:description_html, description_status='ok',
                raw_payload=CAST(:raw_payload AS jsonb), content_hash=:content_hash,
                description_attempts=description_attempts+1,
                description_next_attempt_at=NULL, retrieved_at=now()
            WHERE id=:id
        """), {
            "description_text": normalized.description_text,
            "description_html": normalized.description_html,
            "raw_payload": json.dumps(normalized.raw_payload),
            "content_hash": normalized.content_hash,
            "id": job_id,
        })


async def defer_detail(repo: PollRepository, job_id, raw: dict) -> None:
    async with repo.sessions.begin() as session:
        await session.execute(text("""
            UPDATE jobs SET raw_payload=CAST(:raw_payload AS jsonb),
                description_status='pending', description_attempts=description_attempts+1,
                description_next_attempt_at=now()+interval '5 minutes'
            WHERE id=:id
        """), {"raw_payload": json.dumps(raw), "id": job_id})


async def run(args: argparse.Namespace) -> int:
    if args.rate <= 0 or args.batch_size <= 0:
        raise SystemExit("--rate and --batch-size must be positive")
    repo = PollRepository(PollerConfig.from_env())
    processed = 0
    interval = 1.0 / args.rate
    refresh_lock = await repo.engine.connect()
    try:
        locked = bool((await refresh_lock.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": PollRepository.ADVISORY_LOCK_KEY + 1},
        )).scalar_one())
        if not locked:
            raise SystemExit("another legacy Greenhouse refresh is already running")
        async with AsyncBoardFetcher(concurrency=max(1, min(16, int(args.rate) or 1))) as fetcher:
            while args.limit is None or processed < args.limit:
                size = min(args.batch_size, (args.limit - processed) if args.limit is not None else args.batch_size)
                rows = await claim_batch(repo, size)
                if not rows:
                    break
                for row in rows:
                    started = time.monotonic()
                    raw = {"id": row["external_id"].removeprefix("greenhouse_")}
                    board = BoardSpec(id=row["board_id"], ats="greenhouse", slug=row["slug"])
                    detail, ok = await fetcher.fetch_greenhouse_detail(board, raw)
                    if ok:
                        await save_detail(repo, row["job_id"], normalize_job("greenhouse", row["slug"], detail))
                    else:
                        await defer_detail(repo, row["job_id"], raw)
                    processed += 1
                    await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))
    finally:
        await refresh_lock.close()
        await repo.close()
    print(f"legacy_greenhouse_processed={processed}")
    return processed


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
