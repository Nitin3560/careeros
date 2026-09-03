import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_linkedin_jobs  # noqa: E402


def test_ingest_linkedin_jobs_saves_fetch_results(monkeypatch, capsys):
    saved = {}

    class FakeSession:
        def close(self):
            saved["closed"] = True

    monkeypatch.setattr(
        ingest_linkedin_jobs,
        "fetch_linkedin_jobs",
        lambda query: [{"external_id": f"linkedin_{query}"}],
    )
    monkeypatch.setattr(ingest_linkedin_jobs, "SessionLocal", lambda: FakeSession())

    def fake_save_jobs(db, jobs):
        saved["jobs"] = jobs
        return {"inserted": 1, "skipped": 0}

    monkeypatch.setattr(ingest_linkedin_jobs, "save_jobs", fake_save_jobs)
    monkeypatch.setattr(sys, "argv", ["ingest_linkedin_jobs.py", "--query", "ai-infra"])

    ingest_linkedin_jobs.main()

    assert saved["jobs"] == [{"external_id": "linkedin_ai-infra"}]
    assert saved["closed"] is True
    output = capsys.readouterr().out
    assert "fetched 1 linkedin jobs" in output
    assert "inserted 1" in output
