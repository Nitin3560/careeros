import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_public_sources  # noqa: E402


def test_probe_company_uses_known_source(monkeypatch):
    calls = []

    def fake_probe_candidate(client, source, slug):
        calls.append((source, slug))
        return 7

    monkeypatch.setattr(probe_public_sources, "probe_candidate", fake_probe_candidate)

    result = probe_public_sources.probe_company("Cloudflare", timeout=1)

    assert result == {
        "company": "Cloudflare",
        "status": "found",
        "source": "greenhouse",
        "slug": "cloudflare",
        "job_count": 7,
    }
    assert calls == [("greenhouse", "cloudflare")]


def test_probe_company_returns_not_found_when_candidates_fail(monkeypatch):
    monkeypatch.setattr(
        probe_public_sources,
        "KNOWN_PUBLIC_SOURCES",
        {"example": [("greenhouse", "example"), ("lever", "example")]},
    )
    monkeypatch.setattr(
        probe_public_sources,
        "probe_candidate",
        lambda client, source, slug: 0,
    )

    assert probe_public_sources.probe_company("Example", timeout=1) == {
        "company": "Example",
        "status": "not_found",
    }
