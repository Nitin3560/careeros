#!/usr/bin/env python3
"""Poll a small real-board sample into an explicitly supplied database."""
import argparse
import asyncio
from dataclasses import replace
import re
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.ingestion.poller.config import PollerConfig  # noqa: E402
from app.ingestion.poller.fetcher import AsyncBoardFetcher  # noqa: E402
from app.ingestion.poller.normalization import external_id, normalize_job, stable_list_hash  # noqa: E402
from app.ingestion.poller.repository import PollRepository  # noqa: E402
from app.ingestion.poller.types import BoardSpec, BoardWrite  # noqa: E402


def async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


async def select_boards(repo: PollRepository, per_source: int) -> list[BoardSpec]:
    boards = []
    async with repo.sessions() as session:
        for ats in ("greenhouse", "lever", "ashby"):
            rows = (await session.execute(text("""
                SELECT id, ats, slug, tier, status, etag, last_modified, list_hash,
                       consecutive_failures, not_found_count, empty_since
                FROM ats_boards WHERE ats=:ats AND status='live'
                ORDER BY last_success_at DESC NULLS LAST LIMIT :limit
            """), {"ats": ats, "limit": per_source})).mappings().all()
            boards.extend(BoardSpec(**dict(row)) for row in rows)
        amazon = (await session.execute(text("""
            SELECT id, ats, slug, tier, status, etag, last_modified, list_hash,
                   consecutive_failures, not_found_count, empty_since
            FROM ats_boards WHERE ats='amazon' LIMIT 1
        """))).mappings().one_or_none()
        if amazon:
            boards.append(BoardSpec(**dict(amazon)))
    return boards


async def main_async(args) -> int:
    config = PollerConfig.from_env(async_url(args.database_url))
    repo = PollRepository(config)
    failures = 0
    try:
        boards = await select_boards(repo, args.per_source)
        if not boards:
            print("no eligible smoke-test boards found")
            return 1
        async with AsyncBoardFetcher(config.concurrency, config.user_agent) as fetcher:
            for board in boards:
                result = await fetcher.fetch_board(board, amazon_pages=1 if board.ats == "amazon" else None)
                if not result.complete:
                    print(f"{board.ats}/{board.slug}: failed {result.error}")
                    failures += 1
                    continue
                state = await repo.board_job_state(board.id)
                fetched_ids = {external_id(board.ats, raw) for raw in result.jobs}
                normalized = []
                details = 0
                for raw in result.jobs:
                    pending = False
                    payload = raw
                    if board.ats == "greenhouse":
                        details += 1
                        payload, ok = await fetcher.fetch_greenhouse_detail(board, raw)
                        pending = not ok
                    normalized.append(normalize_job(board.ats, board.slug, payload, pending=pending))
                result = replace(result, detail_fetches=details)
                outcome = await repo.write_board(BoardWrite(
                    result=result, jobs=normalized, fetched_ids=fetched_ids,
                    list_hash=stable_list_hash(board.ats, result.jobs),
                ))
                nonempty = sum(bool(job.description_text) for job in normalized)
                headings = sum(any(
                    line.startswith("## ") and bool(line[3:].strip())
                    for line in job.description_text.splitlines()
                ) for job in normalized)
                leftovers = sum(bool(re.search(r"<[^>]+>|&(?:[A-Za-z]+|#[0-9]+);", job.description_text)) for job in normalized)
                count = max(len(normalized), 1)
                print(
                    f"{board.ats}/{board.slug}: {outcome.status} jobs={len(result.jobs)} "
                    f"nonempty={100*nonempty/count:.1f}% headings={100*headings/count:.1f}% "
                    f"leftover_markup={leftovers}"
                )
                for sample in normalized[:2]:
                    print(f"  SAMPLE {sample.title}:\n{sample.description_text[:700]}\n")
                if normalized and (nonempty / count < 0.99 or leftovers):
                    failures += 1
    finally:
        await repo.close()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--per-source", type=int, default=6)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
