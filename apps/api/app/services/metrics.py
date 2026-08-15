from threading import Lock
from time import time

_lock = Lock()
_started_at = time()
_request_count = 0
_error_count = 0
_total_latency_ms = 0.0
_routes: dict[str, dict[str, float | int]] = {}


def record_http_request(
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
) -> None:
    global _request_count, _error_count, _total_latency_ms

    route_key = f"{method} {path}"
    with _lock:
        _request_count += 1
        _total_latency_ms += latency_ms
        if status_code >= 500:
            _error_count += 1

        route = _routes.setdefault(
            route_key,
            {"count": 0, "errors": 0, "total_latency_ms": 0.0},
        )
        route["count"] += 1
        route["total_latency_ms"] += latency_ms
        if status_code >= 500:
            route["errors"] += 1


def metrics_snapshot() -> dict:
    with _lock:
        average_latency_ms = (
            _total_latency_ms / _request_count if _request_count else 0.0
        )
        routes = {}
        for key, values in _routes.items():
            count = values["count"]
            routes[key] = {
                "count": count,
                "errors": values["errors"],
                "average_latency_ms": round(
                    values["total_latency_ms"] / count, 2
                )
                if count
                else 0.0,
            }

        return {
            "uptime_seconds": round(time() - _started_at, 2),
            "request_count": _request_count,
            "error_count": _error_count,
            "average_latency_ms": round(average_latency_ms, 2),
            "routes": routes,
        }
