from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import random
import time

from sqlalchemy.exc import SQLAlchemyError

from .config import PollerConfig
from .fetcher import AsyncBoardFetcher
from .normalization import external_id, normalize_job, stable_list_hash
from .repository import PollRepository
from .types import BoardSpec, BoardWrite, FetchResult, WriteStats


logger = logging.getLogger("careeros.poller")


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({"event": event, "time": datetime.now(timezone.utc).isoformat(), **fields}, default=str))


class PollScheduler:
    def __init__(self, config: PollerConfig, repository: PollRepository | None = None):
        self.config = config
        self.repository = repository or PollRepository(config)
        self.stop_event = asyncio.Event()

    async def run_forever(self) -> None:
        acquired = await self._acquire_instance_lock_with_retry()
        if acquired is None:
            await self.repository.close()
            return
        if not acquired:
            log_event("poller_instance_lock_unavailable", severity="error")
            await self.repository.close()
            raise RuntimeError("another CareerOS poller is already running")
        try:
            async with AsyncBoardFetcher(
                self.config.concurrency, self.config.user_agent, self.config.workday_max_pages
            ) as fetcher:
                await asyncio.gather(*(
                    self._worker_loop(fetcher, worker_id)
                    for worker_id in range(self.config.batch_workers)
                ))
        finally:
            await self.repository.close()

    async def _acquire_instance_lock_with_retry(self) -> bool | None:
        error_backoff = 5.0
        while not self.stop_event.is_set():
            try:
                return await self.repository.acquire_instance_lock()
            except (SQLAlchemyError, OSError, ConnectionError) as exc:
                log_event(
                    "poller_database_retry", severity="error", worker="instance_lock",
                    error=f"{type(exc).__name__}: {exc}"[:500], retry_seconds=error_backoff,
                )
                await self._wait_or_stop(error_backoff)
                error_backoff = min(60.0, error_backoff * 2)
        return None

    async def _wait_or_stop(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def _worker_loop(self, fetcher: AsyncBoardFetcher, worker_id: int) -> None:
        error_backoff = 5.0
        while not self.stop_event.is_set():
            try:
                polled = await self.run_cycle(fetcher)
            except (SQLAlchemyError, OSError, ConnectionError) as exc:
                log_event(
                    "poller_database_retry", severity="error", worker=worker_id,
                    error=f"{type(exc).__name__}: {exc}"[:500], retry_seconds=error_backoff,
                )
                await self._wait_or_stop(error_backoff)
                error_backoff = min(60.0, error_backoff * 2)
                continue
            error_backoff = 5.0
            if polled == 0:
                await self._wait_or_stop(random.uniform(5.0, 15.0))

    async def run_cycle(self, fetcher: AsyncBoardFetcher | None = None) -> int:
        owns_fetcher = fetcher is None
        if owns_fetcher:
            fetcher = AsyncBoardFetcher(
                self.config.concurrency, self.config.user_agent, self.config.workday_max_pages
            )
        assert fetcher is not None
        if owns_fetcher:
            await fetcher.__aenter__()
        run_id, boards_due, boards = await self.repository.start_run_and_claim()
        if not boards:
            if owns_fetcher:
                await fetcher.__aexit__(None, None, None)
            return 0

        queue: asyncio.Queue[BoardWrite | None] = asyncio.Queue(self.config.queue_size)
        stats: list[WriteStats] = []

        async def writer() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is None:
                        return
                    try:
                        outcome = await self.repository.write_board(item)
                    except Exception as exc:
                        log_event(
                            "board_write_exception", severity="error",
                            board=item.result.board.slug, error=str(exc),
                        )
                        outcome = WriteStats(status="failed", latency_ms=item.result.latency_ms)
                    stats.append(outcome)
                    log_event("board_written", board=item.result.board.slug, ats=item.result.board.ats, status=outcome.status)
                finally:
                    queue.task_done()

        writers = [asyncio.create_task(writer()) for _ in range(self.config.writer_count)]
        board_sem = asyncio.Semaphore(self.config.concurrency)

        async def guarded_poll(board: BoardSpec) -> None:
            async with board_sem:
                try:
                    await self._poll_one(board, fetcher, queue)
                except Exception as exc:
                    log_event("board_poll_exception", severity="error", board=board.slug, error=str(exc))
                    await queue.put(BoardWrite(result=FetchResult(
                        board=board, complete=False, status_code=None,
                        error=f"{type(exc).__name__}: {exc}"[:500],
                    )))

        await asyncio.gather(*(guarded_poll(board) for board in boards))
        await queue.join()
        for _ in writers:
            await queue.put(None)
        await asyncio.gather(*writers)
        await self.repository.finish_run(run_id, stats)
        await self._retry_pending_details(fetcher)
        self._health_warnings(boards_due, boards, stats)
        health = await self.repository.health_snapshot()
        if health["lagged"]:
            log_event("due_board_lag", severity="warning", lagged_over_20m=health["lagged"])
        if health["ok_rate_1h"] < 0.8:
            log_event("low_ok_rate", severity="warning", ok_rate=health["ok_rate_1h"])
        if health["new_jobs_3h"] == 0:
            log_event("no_new_jobs_3h", severity="warning")
        log_event("cycle_complete", run_id=run_id, boards_due=boards_due, boards_polled=len(stats))
        if owns_fetcher:
            await fetcher.__aexit__(None, None, None)
        return len(stats)

    async def _retry_pending_details(self, fetcher: AsyncBoardFetcher) -> None:
        pending = await self.repository.pending_details(limit=100)
        for row in pending:
            board = BoardSpec(**{
                key: row[key] for key in (
                    "id", "ats", "slug", "tier", "status", "etag", "last_modified",
                    "list_hash", "consecutive_failures", "not_found_count", "empty_since",
                )
            })
            if hasattr(fetcher, "fetch_detail"):
                detail, ok = await fetcher.fetch_detail(board, row["raw_payload"] or {})
            elif board.ats == "workday":
                detail, ok = await fetcher.fetch_workday_detail(board, row["raw_payload"] or {})
            else:
                detail, ok = await fetcher.fetch_greenhouse_detail(board, row["raw_payload"] or {})
            normalized = normalize_job(board.ats, board.slug, detail, pending=not ok)
            await self.repository.finish_pending_detail(
                row["job_id"], normalized, success=ok,
                attempts=int(row["description_attempts"] or 0) + 1,
            )

    async def _poll_one(
        self,
        board: BoardSpec,
        fetcher: AsyncBoardFetcher,
        queue: asyncio.Queue[BoardWrite | None],
    ) -> None:
        result = await fetcher.fetch_board(board)
        if not result.complete or result.not_modified:
            await queue.put(BoardWrite(result=result))
            return
        list_hash = stable_list_hash(board.ats, result.jobs)
        if board.list_hash and list_hash == board.list_hash:
            await queue.put(BoardWrite(result=result, list_hash=list_hash, unchanged_hash=True))
            return

        fetched_ids = {external_id(board.ats, raw) for raw in result.jobs}
        normalized = []
        detail_fetches = 0
        detail_sources = {
            "greenhouse", "workday", "smartrecruiters", "workable",
            "phenom", "eightfold", "oracle", "icims",
        }
        if board.ats in detail_sources:
            state = await self.repository.board_job_state(board.id)
            details: list[dict] = []
            pending: list[dict] = []
            for raw in result.jobs:
                job_id = external_id(board.ats, raw)
                previous = state.get(job_id)
                needs_detail = previous is None or previous[0]
                if board.ats == "greenhouse":
                    needs_detail = needs_detail or (previous[2] and previous[1] != raw.get("updated_at"))
                if not needs_detail:
                    continue
                if len(details) < self.config.detail_cap_per_board:
                    details.append(raw)
                else:
                    pending.append(raw)

            async def fetch_detail(raw: dict):
                if hasattr(fetcher, "fetch_detail"):
                    detail, ok = await fetcher.fetch_detail(board, raw)
                elif board.ats == "workday":
                    detail, ok = await fetcher.fetch_workday_detail(board, raw)
                else:
                    detail, ok = await fetcher.fetch_greenhouse_detail(board, raw)
                return normalize_job(board.ats, board.slug, detail, pending=not ok)

            detail_fetches = len(details)
            if details:
                normalized.extend(await asyncio.gather(*(fetch_detail(raw) for raw in details)))
            normalized.extend(normalize_job(board.ats, board.slug, raw, pending=True) for raw in pending)
        else:
            normalized = [normalize_job(board.ats, board.slug, raw) for raw in result.jobs]
        result = replace(result, detail_fetches=detail_fetches)
        await queue.put(
            BoardWrite(result=result, jobs=normalized, fetched_ids=fetched_ids, list_hash=list_hash)
        )

    @staticmethod
    def _health_warnings(boards_due: int, boards: list[BoardSpec], stats: list[WriteStats]) -> None:
        if boards_due > len(boards):
            log_event("due_board_lag", severity="warning", due=boards_due, claimed=len(boards))
        if stats:
            ok = sum(item.status in {"ok", "empty", "not_modified", "unchanged_hash"} for item in stats)
            if ok / len(stats) < 0.8:
                log_event("low_ok_rate", severity="warning", ok_rate=ok / len(stats))
