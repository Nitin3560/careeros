from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from report_action_queue import QueueItem, action_score, outreach_score  # noqa: E402


def item(company, title, location="Seattle, Washington, USA"):
    return QueueItem(
        queue_key=f"queue:{company}|{title}",
        company=company,
        title=title,
        location=location,
        date_posted=datetime(2026, 9, 19, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 9, 19, 19, tzinfo=timezone.utc),
        application_url="https://example.com/apply",
        source="greenhouse",
    )


def test_action_score_prioritizes_early_career_sde_over_senior():
    now = datetime(2026, 9, 19, 20, tzinfo=timezone.utc)
    early_score, early_reasons = action_score(
        item("stripe", "Software Engineer, Early Career — Immediate Start"), now
    )
    senior_score, senior_reasons = action_score(
        item("stripe", "Senior Software Engineer, Payments"), now
    )

    assert early_score > senior_score
    assert "early-career" in early_reasons
    assert "senior-or-lead" in senior_reasons


def test_action_score_penalizes_defense_itar_risk():
    now = datetime(2026, 9, 19, 20, tzinfo=timezone.utc)
    score, reasons = action_score(
        item("spacex", "Software Development Engineer, Flight Software"), now
    )

    assert score < 0
    assert "defense-itar-risk" in reasons


def test_outreach_score_marks_recruiter_worthy_companies():
    score, reasons = outreach_score(item("reddit", "Software Engineer, Ingestion Platform"))

    assert score > 0
    assert "known-recruiter-market" in reasons
    assert "candidate-fit-title" in reasons
