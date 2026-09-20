from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class BoardSpec:
    id: UUID
    ats: str
    slug: str
    tier: str = "B"
    status: str = "unknown"
    etag: str | None = None
    last_modified: str | None = None
    list_hash: str | None = None
    consecutive_failures: int = 0
    not_found_count: int = 0
    empty_since: datetime | None = None


@dataclass(frozen=True)
class FetchResult:
    board: BoardSpec
    complete: bool
    status_code: int | None
    jobs: list[dict[str, Any]] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    company_display: str | None = None
    not_modified: bool = False
    error: str | None = None
    latency_ms: float = 0
    detail_fetches: int = 0


@dataclass(frozen=True)
class NormalizedJob:
    external_id: str
    source: str
    company: str
    title: str
    location: str | None
    description_text: str
    description_html: str | None
    description_status: str
    application_url: str | None
    date_posted: datetime | None
    raw_payload: dict[str, Any]
    content_hash: str


@dataclass(frozen=True)
class DiffPlan:
    new: frozenset[str]
    present: frozenset[str]
    missing: frozenset[str]
    reappeared: frozenset[str]


@dataclass
class BoardWrite:
    result: FetchResult
    jobs: list[NormalizedJob] = field(default_factory=list)
    fetched_ids: set[str] = field(default_factory=set)
    list_hash: str | None = None
    unchanged_hash: bool = False


@dataclass
class WriteStats:
    status: str
    new_jobs: int = 0
    updated_jobs: int = 0
    expired_jobs: int = 0
    reappeared_jobs: int = 0
    detail_fetches: int = 0
    latency_ms: float = 0
