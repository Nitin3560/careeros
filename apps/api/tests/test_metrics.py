from app.services.metrics import metrics_snapshot, record_http_request


def test_metrics_snapshot_tracks_request_count_and_latency():
    before = metrics_snapshot()["request_count"]

    record_http_request("GET", "/health", 200, 25.0)
    snapshot = metrics_snapshot()

    assert snapshot["request_count"] == before + 1
    assert snapshot["average_latency_ms"] >= 0
    assert snapshot["routes"]["GET /health"]["count"] >= 1


def test_metrics_snapshot_tracks_server_errors():
    before = metrics_snapshot()["error_count"]

    record_http_request("GET", "/broken", 500, 10.0)
    snapshot = metrics_snapshot()

    assert snapshot["error_count"] == before + 1
    assert snapshot["routes"]["GET /broken"]["errors"] >= 1
