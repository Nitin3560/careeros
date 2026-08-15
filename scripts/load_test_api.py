import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib import error, parse, request


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def summarize(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min_ms": round(min(values), 2),
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(percentile(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


def call(method: str, url: str, timeout: float) -> dict:
    started = time.perf_counter()
    req = request.Request(url, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as res:
            body = res.read()
            status = res.status
    except error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "status": None,
            "latency_ms": latency_ms,
            "ok": False,
            "error": str(exc),
        }

    latency_ms = (time.perf_counter() - started) * 1000
    return {
        "status": status,
        "latency_ms": latency_ms,
        "ok": 200 <= status < 400,
        "bytes": len(body),
    }


def endpoint_url(base_url: str, path: str, params: dict | None = None) -> str:
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        return f"{url}?{parse.urlencode(params)}"
    return url


def run_endpoint(
    name: str,
    method: str,
    url: str,
    requests_count: int,
    concurrency: int,
    timeout: float,
) -> dict:
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(call, method, url, timeout) for _ in range(requests_count)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    latencies = [result["latency_ms"] for result in results if result["ok"]]
    failures = [result for result in results if not result["ok"]]
    statuses = {}
    for result in results:
        status = str(result["status"])
        statuses[status] = statuses.get(status, 0) + 1

    return {
        "name": name,
        "method": method,
        "url": url,
        "requests": requests_count,
        "concurrency": concurrency,
        "successes": len(latencies),
        "failures": len(failures),
        "statuses": statuses,
        "latency": summarize(latencies),
        "sample_error": failures[0].get("error") if failures else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--user-id")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output")
    args = parser.parse_args()

    endpoints = [
        ("health", "GET", endpoint_url(args.base_url, "/health")),
        ("metrics", "GET", endpoint_url(args.base_url, "/metrics")),
        (
            "jobs",
            "GET",
            endpoint_url(args.base_url, "/jobs", {"limit": 20, "offset": 0}),
        ),
    ]
    if args.user_id:
        endpoints.extend(
            [
                (
                    "matches_count",
                    "GET",
                    endpoint_url(args.base_url, f"/users/{args.user_id}/matches/count"),
                ),
                (
                    "cached_matches",
                    "GET",
                    endpoint_url(
                        args.base_url,
                        f"/users/{args.user_id}/matches/cached",
                        {"offset": 0, "limit": 10},
                    ),
                ),
            ]
        )

    started = time.perf_counter()
    results = [
        run_endpoint(
            name,
            method,
            url,
            args.requests,
            args.concurrency,
            args.timeout,
        )
        for name, method, url in endpoints
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "parameters": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "timeout": args.timeout,
            "user_id": args.user_id,
        },
        "duration_seconds": round(time.perf_counter() - started, 2),
        "results": results,
    }
    if all(result["successes"] == 0 for result in results):
        payload["note"] = "No successful requests. Confirm the API server is running and reachable."

    text = json.dumps(payload, indent=2)
    print(text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
