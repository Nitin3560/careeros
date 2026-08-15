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
    monkeypatch.setattr("app.main.create_background_job", lambda *args, **kwargs: created_job)
    monkeypatch.setattr("app.main.set_queue_job_id", fake_set_queue_job_id)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).post("/ingest/greenhouse/bulk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(created_job.id)
    assert response.json()["queue_job_id"] == "rq-job-1"
    assert queued["background_job_id"] == str(created_job.id)
    assert queued["job_timeout"] == 900
