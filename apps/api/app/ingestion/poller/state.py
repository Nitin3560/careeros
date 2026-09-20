from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

from .types import BoardSpec


BASE_INTERVALS = {"A": 900, "B": 3600, "dormant": 10800}


def next_interval_seconds(
    tier: str,
    consecutive_failures: int = 0,
    *,
    jitter: bool = True,
    rng: random.Random | None = None,
) -> int:
    if consecutive_failures >= 5:
        base = min(21600, 900 * (2 ** consecutive_failures))
    else:
        base = BASE_INTERVALS.get(tier, 3600)
    if not jitter:
        return base
    source = rng or random
    return max(60, int(base * source.uniform(0.9, 1.1)))


def next_board_state(
    board: BoardSpec,
    *,
    success: bool,
    status_code: int | None,
    job_count: int | None,
    now: datetime | None = None,
) -> tuple[str, str, int, int, datetime | None]:
    current = now or datetime.now(timezone.utc)
    if not success:
        not_found = board.not_found_count + 1 if status_code in {404, 410} else 0
        status = "dead" if not_found >= 2 else ("failing" if board.consecutive_failures + 1 >= 5 else board.status)
        return status, board.tier, board.consecutive_failures + 1, not_found, board.empty_since

    if job_count:
        tier = "B" if board.tier == "dormant" else board.tier
        return "live", tier, 0, 0, None

    empty_since = board.empty_since or current
    dormant = current - empty_since >= timedelta(days=30)
    return ("dormant" if dormant else "empty"), ("dormant" if dormant else board.tier), 0, 0, empty_since
