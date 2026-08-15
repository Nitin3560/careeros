import uuid

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def test_cached_matches_endpoint_returns_cached_results(monkeypatch):
    user_id = uuid.uuid4()
    profile = object()
    cached_results = [
        {
            "job_id": str(uuid.uuid4()),
            "job_title": "Robotics Engineer",
            "company": "waymo",
            "location": "Mountain View",
            "application_url": "https://example.com",
            "match": {
                "overall_score": 70,
                "strengths": ["ROS 2"],
                "missing": [],
                "confidence": "medium",
                "estimated": False,
            },
        }
    ]

    class FakeQuery:
        def filter(self, *args):
            return self

        def first(self):
            return profile

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    def fake_get_db():
        yield FakeDb()

    def fake_get_cached_matches(db, requested_user_id, requested_profile, offset, page_size):
        assert requested_user_id == str(user_id)
        assert requested_profile is profile
        assert offset == 10
        assert page_size == 5
        return cached_results

    monkeypatch.setattr("app.main.get_cached_matches", fake_get_cached_matches)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        response = TestClient(app).get(
            f"/users/{user_id}/matches/cached?offset=10&limit=5"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "offset": 10,
        "limit": 5,
        "count": 1,
        "has_more": False,
        "results": cached_results,
    }
