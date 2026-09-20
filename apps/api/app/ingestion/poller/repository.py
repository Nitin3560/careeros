from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from typing import Iterable
import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.services.job_ingestion.persist import build_identity_key, build_queue_key, canonicalize_url

from .config import PollerConfig
from .diff import build_diff
from .normalization import NORMALIZER_VERSION
from .state import next_board_state, next_interval_seconds
from .types import BoardSpec, BoardWrite, WriteStats


class PollRepository:
    ADVISORY_LOCK_KEY = 0x4341524545524F53

    def __init__(self, config: PollerConfig, engine: AsyncEngine | None = None):
        self.config = config
        self.engine = engine or create_async_engine(
            config.database_url, pool_size=8, max_overflow=4, pool_pre_ping=True
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self._lock_connection = None

    async def acquire_instance_lock(self) -> bool:
        self._lock_connection = await self.engine.connect()
        acquired = bool((await self._lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": self.ADVISORY_LOCK_KEY}
        )).scalar_one())
        if not acquired:
            await self._lock_connection.close()
            self._lock_connection = None
        return acquired

    async def release_instance_lock(self) -> None:
        if self._lock_connection is not None:
            await self._lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": self.ADVISORY_LOCK_KEY}
            )
            await self._lock_connection.close()
            self._lock_connection = None

    async def close(self) -> None:
        await self.release_instance_lock()
        await self.engine.dispose()

    async def start_run_and_claim(self) -> tuple[uuid.UUID, int, list[BoardSpec]]:
        now = datetime.now(timezone.utc)
        run_id = uuid.uuid4()
        async with self.sessions.begin() as session:
            filters = [
                "next_poll_at <= :now",
                "(status <> 'dead' OR last_ingested_at <= :dead_cutoff)",
            ]
            params: dict = {"now": now, "dead_cutoff": now - timedelta(days=7), "run_id": run_id}
            if self.config.ats_filter:
                filters.append("ats = :ats")
                params["ats"] = self.config.ats_filter
            where = " AND ".join(filters)
            due = int(
                (await session.execute(text(f"SELECT count(*) FROM ats_boards WHERE {where}"), params)).scalar_one()
            )
            limit = self.config.board_limit or self.config.batch_size
            params["limit"] = limit
            rows = (
                await session.execute(
                    text(
                        f"""
                        SELECT id, ats, slug, tier, status, etag, last_modified, list_hash,
                               consecutive_failures, not_found_count, empty_since
                        FROM ats_boards
                        WHERE {where}
                        ORDER BY CASE tier WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE 2 END,
                                 next_poll_at
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                        """
                    ),
                    params,
                )
            ).mappings().all()
            ids = [row["id"] for row in rows]
            if ids:
                p95_ms = (await session.execute(text(
                    "SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY p95_ms) "
                    "FROM poll_runs WHERE finished_at >= now()-interval '24 hours' AND p95_ms IS NOT NULL"
                ))).scalar_one_or_none()
                lease_seconds = max(900, 3 * float(p95_ms or 0) / 1000)
                lease = now + timedelta(seconds=lease_seconds)
                await session.execute(
                    text("UPDATE ats_boards SET next_poll_at = :lease WHERE id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"lease": lease, "ids": ids},
                )
            await session.execute(
                text("INSERT INTO poll_runs (id, started_at, boards_due) VALUES (:id, :started, :due)"),
                {"id": run_id, "started": now, "due": due},
            )
        return run_id, due, [BoardSpec(**dict(row)) for row in rows]

    async def board_job_ids(self, board_id: uuid.UUID) -> tuple[set[str], set[str]]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    text("SELECT external_id, expired_at FROM jobs WHERE board_id = :board_id"),
                    {"board_id": board_id},
                )
            ).all()
        active = {row[0] for row in rows if row[1] is None}
        expired = {row[0] for row in rows if row[1] is not None}
        return active, expired

    async def board_job_state(self, board_id: uuid.UUID) -> dict[str, tuple[bool, object, bool]]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    text("SELECT external_id, expired_at, raw_payload FROM jobs WHERE board_id = :board_id"),
                    {"board_id": board_id},
                )
            ).all()
        return {
            row[0]: (row[1] is not None, (row[2] or {}).get("updated_at"), row[2] is not None)
            for row in rows
        }

    async def write_board(self, write: BoardWrite, *, update_board_state: bool = True) -> WriteStats:
        result = write.result
        now = datetime.now(timezone.utc)
        job_now = now.replace(tzinfo=None)
        if not result.complete:
            return await self._record_failure(result, now)
        if result.not_modified or write.unchanged_hash:
            status = "not_modified" if result.not_modified else "unchanged_hash"
            await self._record_unchanged(write, now)
            return WriteStats(status=status, detail_fetches=result.detail_fetches, latency_ms=result.latency_ms)

        async with self.sessions.begin() as session:
            rows = (
                await session.execute(
                    text("SELECT external_id, expired_at, content_hash FROM jobs WHERE board_id = :board_id FOR UPDATE"),
                    {"board_id": result.board.id},
                )
            ).all()
            active = {row[0] for row in rows if row[1] is None}
            expired = {row[0] for row in rows if row[1] is not None}
            hashes = {row[0]: row[2] for row in rows}
            fetched = write.fetched_ids or {job.external_id for job in write.jobs}
            plan = build_diff(fetched, active, expired)

            by_id = {job.external_id: job for job in write.jobs}
            new_rows = [self._job_values(by_id[job_id], result.board.id, now) for job_id in plan.new if job_id in by_id]
            if new_rows:
                await session.execute(
                    text(
                        """
                        INSERT INTO jobs
                            (id, external_id, source, company, title, location, description_text,
                             description_html, description_status, description_normalizer_version,
                             raw_payload, content_hash,
                             description_attempts, description_next_attempt_at,
                             application_url, canonical_url, identity_key, queue_key, date_posted,
                             board_id, retrieved_at, first_seen_at, last_seen_at, last_verified_at,
                             ingestion_status, seen_count)
                        VALUES
                            (:id, :external_id, :source, :company, :title, :location, :description_text,
                             :description_html, :description_status, :description_normalizer_version,
                             CAST(:raw_payload AS jsonb), :content_hash,
                             :description_attempts, :description_next_attempt_at,
                             :application_url, :canonical_url, :identity_key, :queue_key, :date_posted,
                             :board_id, :retrieved_at, :first_seen_at, :last_seen_at, :last_verified_at,
                             'new', 1)
                        """
                    ),
                    new_rows,
                )

            changed = [
                self._job_values(by_id[job_id], result.board.id, now)
                for job_id in plan.present | plan.reappeared
                if job_id in by_id and (hashes.get(job_id) != by_id[job_id].content_hash or job_id in plan.reappeared)
            ]
            if changed:
                await session.execute(
                    text(
                        """
                        UPDATE jobs SET
                            title=:title, location=:location, description_text=:description_text,
                            description_html=:description_html, description_status=:description_status,
                            description_normalizer_version=:description_normalizer_version,
                            description_attempts=:description_attempts,
                            description_next_attempt_at=:description_next_attempt_at,
                            raw_payload=CAST(:raw_payload AS jsonb), content_hash=:content_hash,
                            application_url=:application_url, canonical_url=:canonical_url,
                            identity_key=:identity_key, queue_key=:queue_key, date_posted=:date_posted,
                            retrieved_at=:retrieved_at, last_seen_at=:last_seen_at,
                            last_verified_at=:last_verified_at, expired_at=NULL,
                            ingestion_status='active', seen_count=seen_count + 1
                        WHERE external_id=:external_id AND board_id=:board_id
                        """
                    ),
                    changed,
                )
            unchanged_present = set(plan.present) - {row["external_id"] for row in changed}
            if unchanged_present:
                await session.execute(
                    text(
                        """
                        UPDATE jobs SET last_seen_at=:now, last_verified_at=:now,
                                        seen_count=seen_count + 1
                        WHERE board_id=:board_id AND external_id IN :ids
                        """
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"now": job_now, "board_id": result.board.id, "ids": list(unchanged_present)},
                )
            expired_count = 0
            if self.config.expiry_enabled and plan.missing:
                update = await session.execute(
                    text(
                        """
                        UPDATE jobs SET expired_at=:now, ingestion_status='expired'
                        WHERE board_id=:board_id AND expired_at IS NULL AND external_id IN :ids
                        """
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"now": job_now, "board_id": result.board.id, "ids": list(plan.missing)},
                )
                expired_count = update.rowcount or 0

            if update_board_state:
                status, tier, failures, not_found, empty_since = next_board_state(
                    result.board, success=True, status_code=result.status_code,
                    job_count=len(fetched), now=now,
                )
                interval = next_interval_seconds(tier, failures)
                await session.execute(
                    text(
                        """
                        UPDATE ats_boards SET status=:status, tier=:tier, job_count=:count,
                            last_ingested_at=:now, last_success_at=:now, last_status_code=:code,
                            last_error=NULL, consecutive_failures=:failures,
                            not_found_count=:not_found, empty_since=:empty_since,
                            etag=COALESCE(:etag, etag), last_modified=COALESCE(:last_modified, last_modified),
                            list_hash=:list_hash, company_display=COALESCE(:display, company_display),
                            poll_interval_seconds=:interval, next_poll_at=:next_poll, updated_at=:now
                        WHERE id=:id
                        """
                    ),
                    {
                        "status": status, "tier": tier, "count": len(fetched), "now": now,
                        "code": result.status_code, "failures": failures, "not_found": not_found,
                        "empty_since": empty_since, "etag": result.etag,
                        "last_modified": result.last_modified, "list_hash": write.list_hash,
                        "display": result.company_display, "interval": interval,
                        "next_poll": now + timedelta(seconds=interval), "id": result.board.id,
                    },
                )
        return WriteStats(
            status="empty" if not fetched else "ok",
            new_jobs=len(plan.new),
            updated_jobs=len(changed),
            expired_jobs=expired_count,
            reappeared_jobs=len(plan.reappeared),
            detail_fetches=result.detail_fetches,
            latency_ms=result.latency_ms,
        )

    async def _record_failure(self, result, now: datetime) -> WriteStats:
        status, tier, failures, not_found, empty_since = next_board_state(
            result.board, success=False, status_code=result.status_code, job_count=None, now=now
        )
        interval = 604800 if status == "dead" else next_interval_seconds(tier, failures)
        async with self.sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE ats_boards SET status=:status, tier=:tier, last_ingested_at=:now,
                        last_status_code=:code, last_error=:error,
                        consecutive_failures=:failures, not_found_count=:not_found,
                        empty_since=:empty_since, poll_interval_seconds=:interval,
                        next_poll_at=:next_poll, updated_at=:now WHERE id=:id
                    """
                ),
                {
                    "status": status, "tier": tier, "now": now, "code": result.status_code,
                    "error": result.error, "failures": failures, "not_found": not_found,
                    "empty_since": empty_since, "interval": interval,
                    "next_poll": now + timedelta(seconds=interval), "id": result.board.id,
                },
            )
        return WriteStats(status="dead" if status == "dead" else "failed", latency_ms=result.latency_ms)

    async def _record_unchanged(self, write: BoardWrite, now: datetime) -> None:
        result = write.result
        known_empty = (write.unchanged_hash and not result.jobs) or result.board.status in {"empty", "dormant"}
        status, tier, failures, not_found, empty_since = next_board_state(
            result.board, success=True, status_code=result.status_code,
            job_count=0 if known_empty else 1, now=now,
        )
        interval = next_interval_seconds(tier)
        async with self.sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE ats_boards SET status=:status, tier=:tier, last_ingested_at=:now,
                        last_success_at=:now, last_status_code=:code, last_error=NULL,
                        consecutive_failures=:failures, not_found_count=:not_found,
                        empty_since=:empty_since,
                        etag=COALESCE(:etag, etag), last_modified=COALESCE(:last_modified, last_modified),
                        list_hash=COALESCE(:list_hash, list_hash), poll_interval_seconds=:interval,
                        next_poll_at=:next_poll, updated_at=:now WHERE id=:id
                    """
                ),
                {
                    "status": status, "tier": tier, "now": now, "code": result.status_code,
                    "failures": failures, "not_found": not_found, "empty_since": empty_since,
                    "etag": result.etag,
                    "last_modified": result.last_modified, "list_hash": write.list_hash,
                    "interval": interval, "next_poll": now + timedelta(seconds=interval),
                    "id": result.board.id,
                },
            )

    async def finish_run(self, run_id: uuid.UUID, stats: list[WriteStats]) -> None:
        latencies = sorted(item.latency_ms for item in stats if item.latency_ms >= 0)
        def percentile(fraction: float) -> float | None:
            if not latencies:
                return None
            return latencies[min(len(latencies) - 1, math.ceil(len(latencies) * fraction) - 1)]
        counts = {key: sum(item.status == key for item in stats) for key in (
            "ok", "not_modified", "unchanged_hash", "empty", "failed", "dead"
        )}
        async with self.sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE poll_runs SET finished_at=:finished, boards_polled=:polled,
                        ok=:ok, not_modified=:not_modified, unchanged_hash=:unchanged_hash,
                        empty=:empty, failed=:failed, dead=:dead, new_jobs=:new_jobs,
                        updated_jobs=:updated_jobs, expired_jobs=:expired_jobs,
                        reappeared_jobs=:reappeared_jobs, detail_fetches=:detail_fetches,
                        p50_ms=:p50, p95_ms=:p95 WHERE id=:id
                    """
                ),
                {
                    "finished": datetime.now(timezone.utc), "polled": len(stats), **counts,
                    "new_jobs": sum(item.new_jobs for item in stats),
                    "updated_jobs": sum(item.updated_jobs for item in stats),
                    "expired_jobs": sum(item.expired_jobs for item in stats),
                    "reappeared_jobs": sum(item.reappeared_jobs for item in stats),
                    "detail_fetches": sum(item.detail_fetches for item in stats),
                    "p50": percentile(0.5), "p95": percentile(0.95), "id": run_id,
                },
            )

    async def health_snapshot(self) -> dict:
        async with self.sessions() as session:
            row = (await session.execute(text("""
                SELECT
                  (SELECT count(*) FROM ats_boards
                   WHERE status <> 'dead' AND next_poll_at < now()-interval '20 minutes') AS lagged,
                  (SELECT coalesce(sum(new_jobs),0) FROM poll_runs
                   WHERE started_at >= now()-interval '3 hours') AS new_jobs_3h,
                  (SELECT coalesce(sum(ok+not_modified+unchanged_hash+empty),0)::float /
                          greatest(coalesce(sum(boards_polled),0),1)
                   FROM poll_runs WHERE started_at >= now()-interval '1 hour') AS ok_rate_1h
            """))).mappings().one()
        return dict(row)

    @staticmethod
    def _job_values(job, board_id: uuid.UUID, now: datetime) -> dict:
        job_now = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
        application_url = job.application_url
        identity_data = {
            "company": job.company, "title": job.title, "location": job.location,
            "application_url": application_url,
        }
        canonical = canonicalize_url(application_url)
        identity_data["canonical_url"] = canonical
        return {
            "id": uuid.uuid4(), "external_id": job.external_id, "source": job.source,
            "company": job.company, "title": job.title, "location": job.location,
            "description_text": job.description_text, "description_html": job.description_html,
            "description_status": job.description_status, "raw_payload": json.dumps(job.raw_payload),
            "description_normalizer_version": NORMALIZER_VERSION,
            "content_hash": job.content_hash, "application_url": application_url,
            "description_attempts": 1 if job.description_status == "pending" else 0,
            "description_next_attempt_at": now + timedelta(minutes=5) if job.description_status == "pending" else None,
            "canonical_url": canonical, "identity_key": build_identity_key(identity_data),
            "queue_key": build_queue_key(identity_data), "date_posted": job.date_posted,
            "board_id": board_id, "retrieved_at": job_now, "first_seen_at": job_now,
            "last_seen_at": job_now, "last_verified_at": job_now,
        }

    async def pending_greenhouse_details(self, limit: int = 100) -> list[dict]:
        async with self.sessions.begin() as session:
            rows = (await session.execute(text("""
                SELECT j.id AS job_id, j.raw_payload, j.description_attempts,
                       b.id, b.ats, b.slug, b.tier, b.status, b.etag,
                       b.last_modified, b.list_hash, b.consecutive_failures,
                       b.not_found_count, b.empty_since
                FROM jobs j JOIN ats_boards b ON b.id=j.board_id
                WHERE j.description_status='pending' AND j.source='greenhouse'
                  AND coalesce(j.description_next_attempt_at, now()) <= now()
                ORDER BY j.description_next_attempt_at NULLS FIRST LIMIT :limit
                FOR UPDATE OF j SKIP LOCKED
            """), {"limit": limit})).mappings().all()
            if rows:
                ids = [row["job_id"] for row in rows]
                await session.execute(
                    text("UPDATE jobs SET description_next_attempt_at=now()+interval '5 minutes' WHERE id IN :ids")
                    .bindparams(bindparam("ids", expanding=True)), {"ids": ids}
                )
        return [dict(row) for row in rows]

    async def finish_pending_detail(self, job_id: uuid.UUID, job, *, success: bool, attempts: int) -> None:
        async with self.sessions.begin() as session:
            if success:
                await session.execute(text("""
                    UPDATE jobs SET description_text=:text, description_html=:html,
                        description_status='ok', raw_payload=CAST(:raw AS jsonb), content_hash=:hash,
                        description_normalizer_version=:normalizer_version,
                        description_attempts=:attempts, description_next_attempt_at=NULL
                    WHERE id=:id
                """), {
                    "text": job.description_text, "html": job.description_html,
                    "raw": json.dumps(job.raw_payload), "hash": job.content_hash,
                    "normalizer_version": NORMALIZER_VERSION,
                    "attempts": attempts, "id": job_id,
                })
            else:
                delay = min(21600, 60 * (2 ** attempts))
                await session.execute(text("""
                    UPDATE jobs SET description_attempts=:attempts,
                        description_next_attempt_at=now() + (:delay * interval '1 second')
                    WHERE id=:id
                """), {"attempts": attempts, "delay": delay, "id": job_id})
