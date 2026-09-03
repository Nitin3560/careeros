import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_public_sources  # noqa: E402


def test_probe_company_reports_discovered_source(monkeypatch):
    source = SimpleNamespace(
        source="greenhouse",
        slug="cloudflare",
        fetch=lambda slug: [{"external_id": f"greenhouse_{slug}"}],
    )
    monkeypatch.setattr(
        probe_public_sources,
        "discover_public_source",
        lambda company, probe_unknown: source,
    )

    result = probe_public_sources.probe_company("Cloudflare")

    assert result == {
        "company": "Cloudflare",
        "status": "found",
        "source": "greenhouse",
        "slug": "cloudflare",
        "job_count": 1,
    }


def test_probe_company_returns_not_found_when_candidates_fail(monkeypatch):
    monkeypatch.setattr(
        probe_public_sources,
        "discover_public_source",
        lambda company, probe_unknown: None,
    )

    assert probe_public_sources.probe_company("Example") == {
        "company": "Example",
        "status": "not_found",
    }
