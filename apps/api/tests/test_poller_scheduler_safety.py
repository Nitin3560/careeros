import asyncio
import uuid

import pytest

from app.ingestion.poller.config import PollerConfig
from app.ingestion.poller.repository import PollRepository
from app.ingestion.poller.scheduler import PollScheduler
from app.ingestion.poller.types import BoardSpec, FetchResult


def config(**changes):
    values = {"database_url": "postgresql+asyncpg://unused", "detail_cap_per_board": 200}
    values.update(changes)
    return PollerConfig(**values)


def board():
    return BoardSpec(id=uuid.uuid4(), ats="greenhouse", slug="example")


class Repo:
    def __init__(self, state):
        self.state = state

    async def board_job_state(self, _board_id):
        return self.state


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


def test_slow_batch_does_not_block_next_claim_worker():
    async def scenario():
        scheduler = PollScheduler(config(batch_workers=2), Repo({}))
        fast_claimed = asyncio.Event()
        calls = 0

        async def cycle(_fetcher):
            nonlocal calls
            calls += 1
            current = calls
            if current == 1:
                await asyncio.wait_for(fast_claimed.wait(), 0.5)
                return 1
            if current == 2:
                fast_claimed.set()
                return 1
            return 0

        scheduler.run_cycle = cycle
        assert await scheduler._drain_due_batches(object()) == 2
        assert calls >= 3

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
