import asyncio
import logging
import signal

from .config import PollerConfig
from .scheduler import PollScheduler


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scheduler = PollScheduler(PollerConfig.from_env())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, scheduler.stop_event.set)
    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(run())
