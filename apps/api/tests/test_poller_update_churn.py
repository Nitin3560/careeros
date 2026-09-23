import inspect

from app.ingestion.poller.config import PollerConfig
from app.ingestion.poller.repository import PollRepository


def test_seen_touch_interval_defaults_to_six_hours(monkeypatch):
    monkeypatch.delenv("POLLER_SEEN_TOUCH_INTERVAL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused")
    assert PollerConfig.from_env().seen_touch_interval_seconds == 6 * 60 * 60


def test_present_touch_updates_only_hot_friendly_columns():
    source = inspect.getsource(PollRepository.write_board)
    statement = "UPDATE jobs SET last_seen_at=:now, seen_count=seen_count + 1"
    assert statement in source
    assert "AND last_seen_at < :touch_before" in source


def test_missing_expiry_query_does_not_reference_last_seen_at():
    source = inspect.getsource(PollRepository.write_board)
    expiry = source.split("if plan.missing:", 1)[1].split("if update_board_state", 1)[0]
    assert "missing_count=missing_count + 1" in expiry
    assert "missing_count >= :expiry_threshold" in expiry
    assert "last_seen_at" not in expiry
