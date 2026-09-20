#!/usr/bin/env python3
import asyncio
import logging
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.ingestion.poller import PollerConfig, PollScheduler  # noqa: E402


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scheduler = PollScheduler(PollerConfig.from_env())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, scheduler.stop_event.set)
    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
