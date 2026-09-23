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
from app.ingestion.poller.normalization import normalize_job  # noqa: E402
from app.ingestion.poller.repository import PollRepository  # noqa: E402
from app.ingestion.poller.types import BoardSpec  # noqa: E402

BASE_ATS = ("greenhouse", "lever", "ashby")
NEWER_ATS = (
    "workday", "smartrecruiters", "workable", "phenom",
    "eightfold", "oracle", "icims",
)
DETAIL_ATS = {
    "greenhouse", "workday", "smartrecruiters", "workable",
    "phenom", "eightfold", "oracle", "icims",
}


def board_sample_limit(ats: str, per_source: int) -> int:
    return min(per_source, 3) if ats in NEWER_ATS else per_source


def parse_ats_filter(value: str | None) -> tuple[str, ...]:
    if not value:
        return (*BASE_ATS, *NEWER_ATS, "amazon")
    requested = tuple(dict.fromkeys(
        part.strip().lower() for part in value.split(",") if part.strip()
    ))
    supported = {*BASE_ATS, *NEWER_ATS, "amazon"}
    unknown = sorted(set(requested) - supported)
    if unknown:
        raise ValueError(f"unsupported --ats values: {','.join(unknown)}")
    return requested


def async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


async def select_boards(
    repo: PollRepository, per_source: int, sources: tuple[str, ...]
) -> list[BoardSpec]:
    boards = []
    async with repo.sessions() as session:
        for ats in sources:
            limit = board_sample_limit(ats, per_source)
            rows = (await session.execute(text("""
                SELECT id, ats, slug, tier, status, etag, last_modified, list_hash,
                       consecutive_failures, not_found_count, empty_since
                FROM ats_boards WHERE ats=:ats AND status <> 'dead'
                ORDER BY job_count ASC NULLS LAST, last_success_at DESC NULLS LAST,
                         updated_at DESC LIMIT :limit
            """), {"ats": ats, "limit": limit})).mappings().all()
            boards.extend(BoardSpec(**dict(row)) for row in rows)
    return boards


def fresh_board(board: BoardSpec) -> BoardSpec:
    """Disable conditional requests in memory; never mutate ats_boards."""
    return replace(board, etag=None, last_modified=None, list_hash=None)


def quality_metrics(normalized) -> dict[str, float | int]:
    total = len(normalized)
    denominator = max(total, 1)
    nonempty = sum(bool(job.description_text.strip()) for job in normalized)
    headings = sum(any(
        line.startswith("## ") and bool(line[3:].strip())
        for line in job.description_text.splitlines()
    ) for job in normalized)
    leftovers = sum(bool(re.search(
        r"<[^>]+>|&(?:[A-Za-z]+|#[0-9]+);", job.description_text
    )) for job in normalized)
    return {
        "nonempty": nonempty,
        "headings": headings,
        "leftovers": leftovers,
        "nonempty_pct": 100 * nonempty / denominator,
        "headings_pct": 100 * headings / denominator,
        "leftovers_pct": 100 * leftovers / denominator,
    }


async def main_async(args) -> int:
    config = PollerConfig.from_env(async_url(args.database_url))
    repo = PollRepository(config)
    failures = 0
    try:
        sources = parse_ats_filter(args.ats)
        boards = await select_boards(repo, args.per_source, sources)
        selected_sources = {board.ats for board in boards}
        for ats in sources:
            if ats not in selected_sources:
                print(f"{ats}: status=skipped reason=no boards")
        if not boards:
            print("no eligible smoke-test boards found")
            return 1
        async with AsyncBoardFetcher(config.concurrency, config.user_agent) as fetcher:
            for board in boards:
                selected = fresh_board(board)
                try:
                    result = await fetcher.fetch_board(
                        selected, amazon_pages=1 if board.ats == "amazon" else None
                    )
                    if not result.complete:
                        print(
                            f"{board.ats}/{board.slug}: status=failed "
                            f"http={result.status_code} error={result.error}"
                        )
                        failures += 1
                        continue
                    sample_jobs = result.jobs[:args.job_limit]
                    async def normalize(raw):
                        pending = False
                        payload = raw
                        if board.ats in DETAIL_ATS:
                            payload, ok = await fetcher.fetch_detail(selected, raw)
                            pending = not ok
                        return normalize_job(board.ats, board.slug, payload, pending=pending)

                    normalized = await asyncio.gather(*(normalize(raw) for raw in sample_jobs))
                    metrics = quality_metrics(normalized)
                    print(
                        f"{board.ats}/{board.slug}: status=ok "
                        f"http={result.status_code} jobs={len(result.jobs)} "
                        f"processed={len(normalized)} "
                        f"nonempty={metrics['nonempty_pct']:.1f}% "
                        f"headings={metrics['headings_pct']:.1f}% "
                        f"leftover_markup={metrics['leftovers_pct']:.1f}% "
                        f"({metrics['leftovers']})"
                    )
                    for sample in normalized[:2]:
                        print(f"  SAMPLE {sample.title}:\n{sample.description_text[:700]}\n")
                    if normalized and (
                        metrics["nonempty_pct"] < 99.0 or metrics["leftovers"]
                    ):
                        failures += 1
                except Exception as exc:
                    print(
                        f"{board.ats}/{board.slug}: status=failed "
                        f"error={type(exc).__name__}: {exc}"
                    )
                    failures += 1
    finally:
        await repo.close()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--per-source", type=int, default=3)
    parser.add_argument("--ats", help="comma-separated ATS names")
    parser.add_argument("--job-limit", type=int, default=50)
    args = parser.parse_args()
    if args.job_limit < 1 or args.job_limit > 50:
        parser.error("--job-limit must be between 1 and 50")
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
