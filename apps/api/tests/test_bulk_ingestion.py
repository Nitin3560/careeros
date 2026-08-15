from types import SimpleNamespace

from app.services.job_ingestion import bulk


class FakeQuery:
    def __init__(self, targets):
        self.targets = targets

    def filter(self, *args):
        return self

    def all(self):
        return self.targets


class FakeDb:
    def __init__(self, targets):
        self.targets = targets
        self.commits = 0

    def query(self, model):
        return FakeQuery(self.targets)

    def commit(self):
        self.commits += 1


def test_ingest_active_greenhouse_targets_records_successes_and_failures(monkeypatch):
    good = SimpleNamespace(slug="goodco", source="greenhouse", active=True)
    bad = SimpleNamespace(slug="badco", source="greenhouse", active=True)
    db = FakeDb([good, bad])

    def fake_fetch(slug):
        if slug == "badco":
            raise RuntimeError("missing board")
        return [{"external_id": "greenhouse_1"}]

    monkeypatch.setattr(bulk, "fetch_greenhouse_jobs", fake_fetch)
    monkeypatch.setattr(
        bulk,
        "save_jobs",
        lambda db, jobs: {"inserted": len(jobs), "skipped": 0},
    )

    result = bulk.ingest_active_greenhouse_targets(db)

    assert result["companies_processed"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["total_jobs_inserted"] == 1
    assert good.active
    assert good.last_ingested_at is not None
    assert not bad.active
    assert db.commits == 2
