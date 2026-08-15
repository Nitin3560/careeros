import uuid
from types import SimpleNamespace

from app.workers import matching


class FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *args):
        return self

    def first(self):
        return self.value


class FakeDb:
    def __init__(self, job, profile):
        self.job = job
        self.profile = profile
        self.commits = 0

    def query(self, model):
        if model.__name__ == "BackgroundJob":
            return FakeQuery(self.job)
        return FakeQuery(self.profile)

    def commit(self):
        self.commits += 1

    def refresh(self, record):
        return None

    def close(self):
        return None


def test_run_match_refresh_scores_page_and_marks_job_succeeded(monkeypatch):
    user_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        status="queued",
        attempts=0,
        payload={"user_id": str(user_id), "offset": 20, "limit": 5},
        result=None,
        error=None,
        started_at=None,
        finished_at=None,
    )
    profile = SimpleNamespace(user_id=user_id, data={}, profile_version=1)
    db = FakeDb(job, profile)

    monkeypatch.setattr(matching, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        matching,
        "get_or_create_matches",
        lambda db, user_id, profile, offset, page_size: [
            {"job_id": "1"},
            {"job_id": "2"},
        ],
    )

    result = matching.run_match_refresh(str(job.id))

    assert result == {"offset": 20, "limit": 5, "count": 2, "has_more": False}
    assert job.status == "succeeded"
    assert job.result == result
    assert job.error is None
    assert job.attempts == 1
    assert job.started_at is not None
    assert job.finished_at is not None
