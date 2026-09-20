#!/usr/bin/env python3
"""Local HTTP load test for concurrency, retries, backoff, and bounded memory."""
import argparse
import asyncio
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import random
import resource
import threading
import time

import httpx

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.ingestion.poller.fetcher import AsyncBoardFetcher  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    attempts = 0

    def do_GET(self):
        type(self).attempts += 1
        value = random.random()
        time.sleep(random.uniform(0.005, 0.05))
        if value < 0.01:
            time.sleep(0.3)
            body = b'{"jobs": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass
            return
        if value < 0.03:
            self.send_error(500)
            return
        if value < 0.04:
            self.send_response(429)
            self.send_header("Retry-After", "0.05")
            self.end_headers()
            return
        body = json.dumps({"jobs": [{"id": self.path, "title": "Software Engineer"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


async def run(args, port: int) -> int:
    started = time.monotonic()
    counts = Counter()
    async with AsyncBoardFetcher(args.concurrency, "CareerOS-Load-Test/1.0") as fetcher:
        fetcher.client.timeout = httpx.Timeout(0.1)
        async def one(index: int):
            host = ("greenhouse", "lever", "ashby")[index % 3]
            try:
                response = await fetcher.request(host, f"http://127.0.0.1:{port}/board/{index}")
                counts[str(response.status_code)] += 1
            except Exception as exc:
                counts[type(exc).__name__] += 1
        await asyncio.gather(*(one(index) for index in range(args.boards)))
    elapsed = time.monotonic() - started
    memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if sys.platform != "darwin" else 1024 * 1024)
    print(json.dumps({
        "boards": args.boards, "elapsed_seconds": round(elapsed, 2),
        "requests_per_second": round(args.boards / max(elapsed, 0.001), 2),
        "results": counts, "max_rss_mb": round(memory_mb, 1),
        "http_attempts": Handler.attempts,
    }, default=dict, indent=2))
    success = counts["200"] / args.boards
    passed = (
        success >= 0.95
        and memory_mb <= args.max_memory_mb
        and elapsed <= args.max_seconds
        and Handler.attempts > args.boards
    )
    return 0 if passed else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boards", type=int, default=13000)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-memory-mb", type=float, default=512)
    parser.add_argument("--max-seconds", type=float, default=3600)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        raise SystemExit(asyncio.run(run(args, server.server_address[1])))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
