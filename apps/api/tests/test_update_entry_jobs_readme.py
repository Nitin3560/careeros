from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from update_entry_jobs_readme import (  # noqa: E402
    EntryJob,
    is_entry_full_time_title,
    render_markdown,
    update_readme,
)


def test_entry_title_filter_keeps_full_time_entry_signals():
    assert is_entry_full_time_title("Software Engineer, New Grad")
    assert is_entry_full_time_title("Software Development Engineer I")
    assert is_entry_full_time_title("Engineer I, Backend")
    assert is_entry_full_time_title("Member of Technical Staff")
    assert is_entry_full_time_title("MTS, Platform")


def test_entry_title_filter_excludes_intern_and_senior():
    assert not is_entry_full_time_title("Software Development Engineer Intern")
    assert not is_entry_full_time_title("Senior Software Engineer")
    assert not is_entry_full_time_title("Staff Software Engineer")


def test_render_and_update_marked_readme(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Profile\n\nold\n")
    job = EntryJob(
        company="Stripe",
        title="Software Engineer, Early Career",
        location="San Francisco, Seattle, New York",
        date_posted=datetime(2026, 9, 19, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 9, 19, 19, tzinfo=timezone.utc),
        application_url="https://stripe.com/jobs/search?gh_jid=1",
        source="greenhouse",
    )

    block = render_markdown([job], since_hours=24)
    assert update_readme(readme, block)
    content = readme.read_text()

    assert "<!-- ENTRY_JOBS:START -->" in content
    assert "Software Engineer, Early Career" in content
    assert "[Apply](https://stripe.com/jobs/search?gh_jid=1)" in content
