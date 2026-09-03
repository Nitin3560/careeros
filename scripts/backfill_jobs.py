import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import httpx  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.job_ingestion.persist import save_jobs  # noqa: E402
from app.services.job_ingestion.public_sources import SOURCE_FETCHERS  # noqa: E402

WORKERS = 8
DELAY = 0.15
MAX_FAILURES = 3

_lock = threading.Lock()
_counters = {"live": 0, "empty": 0, "dead": 0, "error": 0, "jobs": 0}


def log(message: str):
    with _lock:
        print(message, flush=True)


def fetch_board(ats: str, slug: str):
    fetch = SOURCE_FETCHERS.get(ats)
    if not fetch:
        return "error", [], f"no fetcher for {ats}"

    time.sleep(DELAY)
    try:
        jobs = fetch(slug)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in {404, 410}:
            return "dead", [], f"http {code}"
        return "error", [], f"http {code}"
    except httpx.HTTPError as exc:
        return "error", [], type(exc).__name__
    except Exception as exc:
        return "error", [], f"{type(exc).__name__}: {exc}"[:200]

    return ("live" if jobs else "empty"), jobs, None


def process(board_id, ats: str, slug: str):
    status, jobs, error = fetch_board(ats, slug)
    db = SessionLocal()
    try:
        board = db.get(models.AtsBoard, board_id)
        if not board:
            return "error", slug, 0, 0

        inserted = 0
        if status == "live":
            inserted = save_jobs(db, jobs)["inserted"]

        board.status = status
        board.job_count = len(jobs)
        board.last_ingested_at = datetime.now(timezone.utc)
        board.last_error = error
        board.consecutive_failures = (
            board.consecutive_failures + 1 if status == "error" else 0
        )
        if board.consecutive_failures >= MAX_FAILURES:
            board.status = "dead"
        db.commit()

        with _lock:
            _counters[status if status in _counters else "error"] += 1
            _counters["jobs"] += inserted
        return status, slug, len(jobs), inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ats")
    parser.add_argument("--stale-days", type=int)
    parser.add_argument("--include-dead", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(models.AtsBoard.id, models.AtsBoard.ats, models.AtsBoard.slug)
        if args.stale_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.stale_days)
            query = query.filter(
                (models.AtsBoard.last_ingested_at.is_(None))
                | (models.AtsBoard.last_ingested_at < cutoff)
            )
        else:
            query = query.filter(models.AtsBoard.last_ingested_at.is_(None))

        if not args.include_dead:
            query = query.filter(models.AtsBoard.status != "dead")
        if args.ats:
            query = query.filter(models.AtsBoard.ats == args.ats)
        if args.limit:
            query = query.limit(args.limit)

        boards = query.all()
    finally:
        db.close()

    total = len(boards)
    print(f"{total} boards to process ({WORKERS} workers)\n")
    started = time.time()

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(process, *board): board for board in boards}
        for future in as_completed(futures):
            done += 1
            try:
                status, slug, count, inserted = future.result()
            except Exception as exc:
                log(f"[{done}/{total}] worker error {exc}")
                continue
            if done % 50 == 0 or status == "live":
                rate = done / max(time.time() - started, 1)
                eta = (total - done) / max(rate, 0.01) / 60
                log(
                    f"[{done}/{total}] {status:<5} {slug:<28} "
                    f"{count:>5} jobs (+{inserted}) eta {eta:.0f}m"
                )

    minutes = (time.time() - started) / 60
    print(f"\ndone in {minutes:.1f}m")
    for key, value in _counters.items():
        print(f"{key:<8} {value}")


if __name__ == "__main__":
    main()
