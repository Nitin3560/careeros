from app.services.job_ingestion import greenhouse


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "jobs": [
                {
                    "id": 123,
                    "title": "Robotics Engineer",
                    "location": {"name": "Mountain View, CA"},
                    "content": "<p>Build robots</p>",
                    "absolute_url": "https://example.com/job/123",
                    "updated_at": "2026-08-14T12:30:00Z",
                }
            ]
        }


def test_fetch_greenhouse_jobs_normalizes_public_board_response(monkeypatch):
    requested = {}

    def fake_get(url, timeout):
        requested["url"] = url
        requested["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(greenhouse.httpx, "get", fake_get)

    jobs = greenhouse.fetch_greenhouse_jobs("waymo")

    assert requested == {
        "url": "https://boards-api.greenhouse.io/v1/boards/waymo/jobs?content=true",
        "timeout": 10.0,
    }
    assert jobs[0]["external_id"] == "greenhouse_123"
    assert jobs[0]["source"] == "greenhouse"
    assert jobs[0]["company"] == "waymo"
    assert jobs[0]["title"] == "Robotics Engineer"
    assert jobs[0]["location"] == "Mountain View, CA"
    assert jobs[0]["description_text"] == "<p>Build robots</p>"
    assert jobs[0]["application_url"] == "https://example.com/job/123"
    assert jobs[0]["date_posted"].isoformat() == "2026-08-14T12:30:00+00:00"
