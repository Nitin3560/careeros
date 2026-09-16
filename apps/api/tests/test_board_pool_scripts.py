import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import backfill_jobs  # noqa: E402
import assign_board_priorities  # noqa: E402
import import_boards  # noqa: E402


def test_load_boards_normalizes_archive_json(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(
        json.dumps(
            {
                "greenhouse": ["example"],
                "lever": [{"slug": "leverco"}],
                "ashby": [{"name": "ashbyco"}],
                "unknown": ["skip"],
            }
        )
    )

    assert import_boards.load_boards(str(path)) == [
        ("greenhouse", "example"),
        ("lever", "leverco"),
        ("ashby", "ashbyco"),
    ]


def test_fetch_board_distinguishes_empty_from_dead(monkeypatch):
    monkeypatch.setitem(backfill_jobs.SOURCE_FETCHERS, "empty", lambda slug: [])

    status, jobs, error = backfill_jobs.fetch_board("empty", "example")

    assert status == "empty"
    assert jobs == []
    assert error is None


def test_fetch_board_marks_missing_board_dead(monkeypatch):
    response = httpx.Response(404, request=httpx.Request("GET", "https://example.com"))

    def fake_fetch(slug):
        raise httpx.HTTPStatusError("not found", request=response.request, response=response)

    monkeypatch.setitem(backfill_jobs.SOURCE_FETCHERS, "missing", fake_fetch)

    status, jobs, error = backfill_jobs.fetch_board("missing", "example")

    assert status == "dead"
    assert jobs == []
    assert error == "http 404"


def test_fetch_board_marks_rate_limit_separately(monkeypatch):
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))

    def fake_fetch(slug):
        raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    monkeypatch.setitem(backfill_jobs.SOURCE_FETCHERS, "limited", fake_fetch)

    status, jobs, error = backfill_jobs.fetch_board("limited", "example")

    assert status == "rate_limited"
    assert jobs == []
    assert error == "http 429"


def test_assign_priority_uses_recent_eligible_jobs():
    class FakeDb:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((str(sql), params))

            class Result:
                def fetchall(self):
                    return [("board-1",), ("board-2",)]

            return Result()

    db = FakeDb()

    updated = assign_board_priorities.assign_priority(
        db,
        priority=1,
        limit=100,
        days=30,
    )

    assert updated == 2
    assert "j.eligible IS true" in db.calls[0][0]
    assert "b.ats = r.source" in db.calls[0][0]
    assert db.calls[0][1]["priority"] == 1
