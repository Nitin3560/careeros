from datetime import datetime, timedelta
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from classify_jobs import VERSION, _values_for, classify_pending_batches  # noqa: E402


class Deadlock(Exception):
    sqlstate = "40P01"


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class MemoryDatabase:
    def __init__(self, rows=(), deadlocks=0):
        self.rows = {row["id"]: dict(row) for row in rows}
        self.deadlocks = deadlocks

    def session(self):
        return MemorySession(self)


class MemorySession:
    def __init__(self, database):
        self.database = database

    def execute(self, statement, params):
        sql = str(statement)
        if sql.lstrip().startswith("UPDATE jobs"):
            if self.database.deadlocks:
                self.database.deadlocks -= 1
                raise Deadlock("simulated deadlock")
            for values in params:
                self.database.rows[values["id"]]["classifier_version"] = values["classifier_version"]
            return Result([])

        if any(key.startswith("retry_id_") for key in params):
            requested = {value for key, value in params.items() if key.startswith("retry_id_")}
            rows = [row for job_id, row in self.database.rows.items() if job_id in requested and row["classifier_version"] != params["version"]]
        else:
            skipped = {str(value) for key, value in params.items() if key.startswith("skip_id_")}
            rows = [row for job_id, row in self.database.rows.items() if str(job_id) not in skipped and row["classifier_version"] != params["version"]]
            rows.sort(key=lambda row: (row["first_seen_at"], str(row["id"])))
            rows = rows[:params["batch_size"]]
        rows.sort(key=lambda row: (row["first_seen_at"], str(row["id"])))
        return Result(rows)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _rows(ids, seen):
    return [{
        "id": job_id, "title": "Software Engineer I",
        "description_text": "Requirements: 1+ year of professional software engineering experience.",
        "location": "Austin, TX", "first_seen_at": seen, "classifier_version": None,
    } for job_id in ids]


def test_new_lower_uuid_rows_are_found_on_the_next_batch_pass():
    first_ids = [uuid.uuid4() for _ in range(100)]
    later_lower_ids = [uuid.UUID(int=index + 1) for index in range(100)]
    base = datetime(2026, 9, 23)
    database = MemoryDatabase(_rows(first_ids, base))

    first = classify_pending_batches(database.session, batch_size=31, report=lambda _message: None)
    assert first["classified"] == 100
    database.rows.update({row["id"]: row for row in _rows(later_lower_ids, base + timedelta(minutes=1))})

    second = classify_pending_batches(database.session, batch_size=29, report=lambda _message: None)
    assert second["classified"] == 100
    assert all(row["classifier_version"] == VERSION for row in database.rows.values())


def test_deadlock_retries_with_backoff_then_classifies_batch():
    ids = [uuid.uuid4() for _ in range(2)]
    database = MemoryDatabase(_rows(ids, datetime(2026, 9, 23)), deadlocks=2)
    delays = []
    result = classify_pending_batches(database.session, batch_size=5, sleep=delays.append, report=lambda _message: None)
    assert result["classified"] == 2
    assert result["batches_retried"] == 1
    assert result["batches_skipped"] == 0
    assert delays == [0.5, 1.0]


def test_batch_that_deadlocks_after_all_retries_is_skipped_and_counted():
    ids = [uuid.uuid4() for _ in range(2)]
    database = MemoryDatabase(_rows(ids, datetime(2026, 9, 23)), deadlocks=4)
    result = classify_pending_batches(database.session, batch_size=5, sleep=lambda _delay: None, report=lambda _message: None)
    assert result["classified"] == 0
    assert result["batches_skipped"] == 1
    assert result["batches_retried"] == 1


def test_runner_binds_postgres_array_and_years_basis_fields():
    row = _rows([uuid.uuid4()], datetime(2026, 9, 23))[0]
    values = _values_for(row)
    assert isinstance(values["exclusion_reasons"], list)
    assert values["years_basis"] == "none"
