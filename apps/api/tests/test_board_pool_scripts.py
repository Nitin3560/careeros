import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import backfill_jobs  # noqa: E402
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
