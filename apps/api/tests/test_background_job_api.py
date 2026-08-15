import uuid
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def test_bulk_ingest_endpoint_enqueues_background_job(monkeypatch):
    created_job = SimpleNamespace(
        id=uuid.uuid4(),
        job_type="greenhouse_bulk_ingest",
        status="queued",
        queue_job_id=None,
        dedupe_key="greenhouse_bulk_ingest:greenhouse",
        payload={"source": "greenhouse"},
        result=None,
        error=None,
        attempts=0,
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
        updated_at=datetime.utcnow(),
    )
    queued = {}

    class FakeQueue:
        def enqueue(self, fn, background_job_id, job_timeout):
            queued["fn"] = fn
            queued["background_job_id"] = background_job_id
            queued["job_timeout"] = job_timeout
            return SimpleNamespace(id="rq-job-1")

    def fake_get_db():
        yield object()

    def fake_set_queue_job_id(db, job, queue_job_id):
        job.queue_job_id = queue_job_id
        return job

    monkeypatch.setattr("app.main.get_queue", lambda: FakeQueue())
    monkeypatch.setattr(
        "app.main.get_or_create_background_job", lambda *args, **kwargs: (created_job, True)
    )
    monkeypatch.setattr("app.main.set_queue_job_id", fake_set_queue_job_id)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).post("/ingest/greenhouse/bulk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(created_job.id)
    assert response.json()["queue_job_id"] == "rq-job-1"
    assert response.json()["dedupe_key"] == "greenhouse_bulk_ingest:greenhouse"
    assert queued["background_job_id"] == str(created_job.id)
    assert queued["job_timeout"] == 900


def test_bulk_ingest_endpoint_reuses_active_background_job(monkeypatch):
    existing_job = SimpleNamespace(
        id=uuid.uuid4(),
        job_type="greenhouse_bulk_ingest",
        status="running",
        queue_job_id="rq-existing",
        dedupe_key="greenhouse_bulk_ingest:greenhouse",
        payload={"source": "greenhouse"},
        result=None,
        error=None,
        attempts=1,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        finished_at=None,
        updated_at=datetime.utcnow(),
    )

    class FakeQueue:
        def enqueue(self, *args, **kwargs):
            raise AssertionError("reused jobs should not enqueue again")

    def fake_get_db():
        yield object()

    monkeypatch.setattr("app.main.get_queue", lambda: FakeQueue())
    monkeypatch.setattr(
        "app.main.get_or_create_background_job",
        lambda *args, **kwargs: (existing_job, False),
    )
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).post("/ingest/greenhouse/bulk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(existing_job.id)
    assert response.json()["queue_job_id"] == "rq-existing"


def test_match_refresh_endpoint_enqueues_background_job(monkeypatch):
    user_id = uuid.uuid4()
    created_job = SimpleNamespace(
        id=uuid.uuid4(),
        job_type="match_refresh",
        status="queued",
        queue_job_id=None,
        dedupe_key=f"match_refresh:{user_id}:10:5",
        payload={"user_id": str(user_id), "offset": 10, "limit": 5},
        result=None,
        error=None,
        attempts=0,
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
        updated_at=datetime.utcnow(),
    )
    queued = {}

    class FakeQuery:
        def filter(self, *args):
            return self

        def first(self):
            return object()

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    class FakeQueue:
        def enqueue(self, fn, background_job_id, job_timeout):
            queued["fn"] = fn
            queued["background_job_id"] = background_job_id
            queued["job_timeout"] = job_timeout
            return SimpleNamespace(id="rq-match-job-1")

    def fake_get_db():
        yield FakeDb()

    def fake_get_or_create_background_job(db, job_type, payload, dedupe_key):
        created_job.job_type = job_type
        created_job.payload = payload
        created_job.dedupe_key = dedupe_key
        return created_job, True

    def fake_set_queue_job_id(db, job, queue_job_id):
        job.queue_job_id = queue_job_id
        return job

    monkeypatch.setattr("app.main.get_queue", lambda: FakeQueue())
    monkeypatch.setattr(
        "app.main.get_or_create_background_job", fake_get_or_create_background_job
    )
    monkeypatch.setattr("app.main.set_queue_job_id", fake_set_queue_job_id)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).post(
            f"/users/{user_id}/matches/refresh?offset=10&limit=5"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["job_type"] == "match_refresh"
    assert response.json()["queue_job_id"] == "rq-match-job-1"
    assert response.json()["dedupe_key"] == f"match_refresh:{user_id}:10:5"
    assert response.json()["payload"] == {
        "user_id": str(user_id),
        "offset": 10,
        "limit": 5,
    }
    assert queued["background_job_id"] == str(created_job.id)
    assert queued["job_timeout"] == 900


def test_match_refresh_endpoint_reuses_active_background_job(monkeypatch):
    user_id = uuid.uuid4()
    existing_job = SimpleNamespace(
        id=uuid.uuid4(),
        job_type="match_refresh",
        status="queued",
        queue_job_id="rq-existing-match",
        dedupe_key=f"match_refresh:{user_id}:0:10",
        payload={"user_id": str(user_id), "offset": 0, "limit": 10},
        result=None,
        error=None,
        attempts=0,
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
        updated_at=datetime.utcnow(),
    )

    class FakeQuery:
        def filter(self, *args):
            return self

        def first(self):
            return object()

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    class FakeQueue:
        def enqueue(self, *args, **kwargs):
            raise AssertionError("reused jobs should not enqueue again")

    def fake_get_db():
        yield FakeDb()

    monkeypatch.setattr("app.main.get_queue", lambda: FakeQueue())
    monkeypatch.setattr(
        "app.main.get_or_create_background_job",
        lambda *args, **kwargs: (existing_job, False),
    )
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).post(f"/users/{user_id}/matches/refresh")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(existing_job.id)
    assert response.json()["queue_job_id"] == "rq-existing-match"
