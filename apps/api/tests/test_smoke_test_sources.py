from datetime import datetime
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.ingestion.poller.normalization import normalize_job
from app.ingestion.poller.types import BoardSpec
from scripts.smoke_test_sources import (
    NEWER_ATS, board_sample_limit, fresh_board, parse_ats_filter, quality_metrics,
)


def test_newer_source_smoke_coverage_is_complete():
    assert NEWER_ATS == (
        "workday", "smartrecruiters", "workable", "phenom",
        "eightfold", "oracle", "icims",
    )
    assert all(board_sample_limit(ats, 6) == 3 for ats in NEWER_ATS)
    assert board_sample_limit("greenhouse", 6) == 6


def test_ats_filter_limits_run_to_requested_sources():
    assert parse_ats_filter("workday,oracle,workday") == ("workday", "oracle")


def test_fresh_board_clears_conditionals_only_in_memory():
    original = BoardSpec(
        id=uuid.uuid4(), ats="workday", slug="host|tenant|site",
        tier="A", status="live", etag='"etag"', last_modified="yesterday",
        list_hash="hash", consecutive_failures=2, not_found_count=1,
        empty_since=datetime(2026, 9, 1),
    )
    fresh = fresh_board(original)
    assert (fresh.etag, fresh.last_modified, fresh.list_hash) == (None, None, None)
    assert original.etag == '"etag"'
    assert (fresh.tier, fresh.status, fresh.consecutive_failures) == ("A", "live", 2)


def test_quality_metrics_count_nonempty_headings_and_markup():
    clean = normalize_job("ashby", "acme", {
        "id": "1", "title": "Clean", "descriptionHtml": "<h2>Role</h2><p>Build systems.</p>",
    })
    empty = normalize_job("ashby", "acme", {"id": "2", "title": "Empty"})
    # Construct a leftover marker after normalization to test report accounting.
    dirty = type(clean)(**{**clean.__dict__, "description_text": "bad <tag>"})
    metrics = quality_metrics([clean, empty, dirty])
    assert metrics["nonempty_pct"] == 200 / 3
    assert metrics["headings_pct"] == 100 / 3
    assert metrics["leftovers"] == 1
    assert metrics["leftovers_pct"] == 100 / 3
