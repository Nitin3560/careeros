import asyncio
import uuid

import pytest

from app.ingestion.poller.config import PollerConfig
from app.ingestion.poller.repository import PollRepository
from app.ingestion.poller.normalization import stable_list_hash
from app.ingestion.poller.scheduler import PollScheduler
from app.ingestion.poller.types import BoardSpec, FetchResult


def config(**changes):
    values = {"database_url": "postgresql+asyncpg://unused", "detail_cap_per_board": 200}
    values.update(changes)
    return PollerConfig(**values)


def board():
    return BoardSpec(id=uuid.uuid4(), ats="greenhouse", slug="example")


class Repo:
    def __init__(self, state, unresolved_missing=False):
        self.state = state
        self.unresolved_missing = unresolved_missing

    async def board_job_state(self, _board_id):
        return self.state

    async def board_has_unresolved_missing(self, _board_id):
        return self.unresolved_missing


class Fetcher:
    def __init__(self, jobs):
        self.jobs = jobs
        self.details = []

    async def fetch_board(self, selected):
        return FetchResult(board=selected, complete=True, status_code=200, jobs=self.jobs)

    async def fetch_greenhouse_detail(self, _board, raw):
        self.details.append(raw["id"])
        return {**raw, "content": "<p>detail</p>"}, True


async def poll(state, jobs, *, cap=200):
    scheduler = PollScheduler(config(detail_cap_per_board=cap), Repo(state))
    fetcher = Fetcher(jobs)
    queue = asyncio.Queue()
    await scheduler._poll_one(board(), fetcher, queue)
    return fetcher, await queue.get()


def test_legacy_greenhouse_row_does_not_fetch_detail_but_is_marked_present():
    raw = {"id": 1, "title": "Engineer", "updated_at": "new"}
    fetcher, write = asyncio.run(poll({"greenhouse_1": (False, None, False)}, [raw]))
    assert fetcher.details == []
    assert write.fetched_ids == {"greenhouse_1"}
    assert write.jobs == []


def test_new_and_updated_greenhouse_rows_fetch_details():
    jobs = [
        {"id": 1, "title": "New", "updated_at": "v1"},
        {"id": 2, "title": "Changed", "updated_at": "v2"},
    ]
    fetcher, write = asyncio.run(poll({"greenhouse_2": (False, "v1", True)}, jobs))
    assert set(fetcher.details) == {1, 2}
    assert {job.external_id for job in write.jobs} == {"greenhouse_1", "greenhouse_2"}


def test_detail_cap_stores_overflow_as_pending():
    jobs = [{"id": value, "title": f"Job {value}"} for value in range(3)]
    fetcher, write = asyncio.run(poll({}, jobs, cap=1))
    assert len(fetcher.details) == 1
    assert sum(job.description_status == "pending" for job in write.jobs) == 2


def test_workday_detail_cap_stores_overflow_as_pending():
    class WorkdayFetcher(Fetcher):
        async def fetch_workday_detail(self, _board, raw):
            self.details.append(raw["jobReqId"])
            return {**raw, "jobDescription": "<p>detail</p>"}, True

    async def scenario():
        selected = BoardSpec(
            id=uuid.uuid4(), ats="workday",
            slug="acme.wd5.myworkdayjobs.com|acme|External",
        )
        jobs = [{
            "jobReqId": f"R{value}", "externalPath": f"/job/{value}",
            "title": f"Job {value}", "_workday_tenant": "acme",
            "_workday_host": "acme.wd5.myworkdayjobs.com", "_workday_site": "External",
        } for value in range(3)]
        scheduler = PollScheduler(config(detail_cap_per_board=1), Repo({}))
        fetcher = WorkdayFetcher(jobs)
        queue = asyncio.Queue()
        await scheduler._poll_one(selected, fetcher, queue)
        return fetcher, await queue.get()

    fetcher, write = asyncio.run(scenario())
    assert len(fetcher.details) == 1
    assert sum(job.description_status == "pending" for job in write.jobs) == 2


def test_unchanged_list_does_not_skip_unresolved_missing_count_progress():
    async def scenario():
        jobs = [{"id": "present", "title": "Engineer", "descriptionHtml": "<p>Role</p>"}]
        selected = BoardSpec(
            id=uuid.uuid4(), ats="ashby", slug="example",
            list_hash=stable_list_hash("ashby", jobs),
        )
        scheduler = PollScheduler(
            config(expiry_enabled=True), Repo({}, unresolved_missing=True)
        )
        queue = asyncio.Queue()
        await scheduler._poll_one(selected, Fetcher(jobs), queue)
        return await queue.get()

    write = asyncio.run(scenario())
    assert write.unchanged_hash is False
    assert write.fetched_ids == {"ashby_present"}


def test_empty_claim_worker_keeps_running_and_later_claims_due_boards(monkeypatch):
    async def scenario():
        scheduler = PollScheduler(config(batch_workers=1), Repo({}))
        results = iter((0, 1))
        waits = []

        async def cycle(_fetcher):
            result = next(results)
            if result:
                scheduler.stop_event.set()
            return result

        async def wait(delay):
            waits.append(delay)
            await asyncio.sleep(0)

        scheduler.run_cycle = cycle
        scheduler._wait_or_stop = wait
        monkeypatch.setattr("app.ingestion.poller.scheduler.random.uniform", lambda low, high: 7.5)
        await scheduler._worker_loop(object(), 0)
        assert waits == [7.5]

    asyncio.run(scenario())


def test_three_workers_resume_after_all_initial_claims_are_empty():
    async def scenario():
        scheduler = PollScheduler(config(batch_workers=3), Repo({}))
        calls = 0
        claimed = 0
        lock = asyncio.Lock()

        async def cycle(_fetcher):
            nonlocal calls, claimed
            async with lock:
                calls += 1
                if calls <= 3:
                    return 0
                claimed += 1
                if claimed == 3:
                    scheduler.stop_event.set()
                return 1

        async def wait(_delay):
            await asyncio.sleep(0)

        scheduler.run_cycle = cycle
        scheduler._wait_or_stop = wait
        await asyncio.gather(*(
            scheduler._worker_loop(object(), worker_id) for worker_id in range(3)
        ))
        assert calls >= 6
        assert claimed == 3

    asyncio.run(scenario())


def test_database_connection_errors_back_off_and_retry_without_exit():
    async def scenario():
        scheduler = PollScheduler(config(batch_workers=1), Repo({}))
        calls = 0
        waits = []

        async def cycle(_fetcher):
            nonlocal calls
            calls += 1
            if calls <= 2:
                raise OSError("database unavailable")
            scheduler.stop_event.set()
            return 1

        async def wait(delay):
            waits.append(delay)
            await asyncio.sleep(0)

        scheduler.run_cycle = cycle
        scheduler._wait_or_stop = wait
        await scheduler._worker_loop(object(), 0)
        assert calls == 3
        assert waits == [5.0, 10.0]

    asyncio.run(scenario())


def test_instance_lock_database_error_retries_before_startup():
    class FlakyLockRepo(Repo):
        def __init__(self):
            super().__init__({})
            self.calls = 0

        async def acquire_instance_lock(self):
            self.calls += 1
            if self.calls == 1:
                raise OSError("database unavailable")
            return True

    async def scenario():
        repo = FlakyLockRepo()
        scheduler = PollScheduler(config(), repo)
        waits = []

        async def wait(delay):
            waits.append(delay)
            await asyncio.sleep(0)

        scheduler._wait_or_stop = wait
        assert await scheduler._acquire_instance_lock_with_retry() is True
        assert repo.calls == 2
        assert waits == [5.0]

    asyncio.run(scenario())


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Connection:
    def __init__(self, acquired):
        self.acquired = acquired
        self.closed = False

    async def execute(self, *_args, **_kwargs):
        return Scalar(self.acquired)

    async def close(self):
        self.closed = True


class Engine:
    def __init__(self, acquired):
        self.connection = Connection(acquired)

    async def connect(self):
        return self.connection


def test_second_poller_lock_failure_closes_connection():
    async def scenario():
        engine = Engine(False)
        repo = PollRepository(config(), engine=engine)
        assert await repo.acquire_instance_lock() is False
        assert engine.connection.closed
        assert repo._lock_connection is None

    asyncio.run(scenario())


def test_second_poller_instance_exits_before_creating_fetcher():
    class LockedRepo(Repo):
        def __init__(self):
            super().__init__({})
            self.closed = False

        async def acquire_instance_lock(self):
            return False

        async def close(self):
            self.closed = True

    async def scenario():
        repo = LockedRepo()
        scheduler = PollScheduler(config(), repo)
        with pytest.raises(RuntimeError, match="already running"):
            await scheduler.run_forever()
        assert repo.closed

    asyncio.run(scenario())
