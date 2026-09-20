from __future__ import annotations

from dataclasses import dataclass
import os


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PollerConfig:
    database_url: str
    expiry_enabled: bool = False
    retention_enabled: bool = False
    concurrency: int = 64
    board_limit: int | None = None
    ats_filter: str | None = None
    writer_count: int = 4
    queue_size: int = 256
    batch_size: int = 300
    batch_workers: int = 3
    detail_cap_per_board: int = 200
    user_agent: str = "CareerOS-Collector/1.0 (+https://github.com/Nitin3560/careeros)"

    @classmethod
    def from_env(cls, database_url: str | None = None) -> "PollerConfig":
        url = database_url or os.environ["DATABASE_URL"]
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        limit = os.getenv("POLLER_BOARD_LIMIT")
        return cls(
            database_url=url,
            expiry_enabled=_flag("POLLER_EXPIRY_ENABLED"),
            retention_enabled=_flag("POLLER_RETENTION_ENABLED"),
            concurrency=max(1, int(os.getenv("POLLER_CONCURRENCY", "64"))),
            board_limit=int(limit) if limit else None,
            ats_filter=os.getenv("POLLER_ATS") or None,
            writer_count=max(1, int(os.getenv("POLLER_WRITERS", "4"))),
            queue_size=max(8, int(os.getenv("POLLER_QUEUE_SIZE", "256"))),
            batch_size=max(1, int(os.getenv("POLLER_BATCH_SIZE", "300"))),
            batch_workers=max(1, int(os.getenv("POLLER_BATCH_WORKERS", "3"))),
            detail_cap_per_board=max(0, int(os.getenv("POLLER_DETAIL_CAP_PER_BOARD", "200"))),
            user_agent=os.getenv(
                "POLLER_USER_AGENT",
                "CareerOS-Collector/1.0 (+https://github.com/Nitin3560/careeros)",
            ),
        )
