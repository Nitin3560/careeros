import hashlib
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.backfill_job_descriptions import build_updates


def content_hash(title: str, location: str, text: str) -> str:
    return hashlib.sha256("|".join((title, location, text)).encode()).hexdigest()


def test_build_updates_skips_unchanged_content_and_advances_metadata_only():
    job_id = uuid.uuid4()
    rows = [{
        "id": job_id,
        "source": "ashby",
        "title": "Software Engineer I",
        "location": "Remote - US",
        "description_html": "<p>stale duplicate</p>",
        "raw_payload": {"descriptionHtml": "<p>Build systems.</p>"},
        "content_hash": content_hash("Software Engineer I", "Remote - US", "Build systems."),
    }]

    changed, unchanged_ids = build_updates(rows)

    assert changed == []
    assert unchanged_ids == [job_id]


def test_build_updates_rewrites_only_changed_normalized_content():
    job_id = uuid.uuid4()
    rows = [{
        "id": job_id,
        "source": "ashby",
        "title": "Software Engineer I",
        "location": "Remote - US",
        "description_html": None,
        "raw_payload": {"descriptionHtml": "<p>Build&nbsp; systems.</p>"},
        "content_hash": "old",
    }]

    changed, unchanged_ids = build_updates(rows)

    assert unchanged_ids == []
    assert changed[0]["id"] == job_id
    assert changed[0]["text"] == "Build systems."
    assert "html" not in changed[0]
