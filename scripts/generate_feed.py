#!/usr/bin/env python3
"""Generate a self-contained daily HTML feed from classified job rows."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

FEED_SQL = """
SELECT j.id, j.company, j.title, j.location, j.location_class,
       j.is_new_grad_title, j.min_years_required, j.first_seen_at,
       j.application_url, j.content_hash, b.ats,
       b.company_display AS company_display, reg.company_name AS registry_name,
       COALESCE(NULLIF(b.company_display, ''), reg.company_name, j.company) AS display_name
FROM jobs AS j
LEFT JOIN ats_boards AS b ON b.id = j.board_id
LEFT JOIN LATERAL (
    SELECT cr.company_name
    FROM company_registry AS cr
    WHERE cr.board_id = j.board_id
    ORDER BY (cr.detection_status = 'detected') DESC, cr.priority, cr.company_name
    LIMIT 1
) AS reg ON TRUE
WHERE j.expired_at IS NULL
  AND j.first_seen_at >= now() - (:days * interval '1 day')
  AND j.is_tech_title IS TRUE
  AND j.is_senior_title IS FALSE
  AND j.location_class IN ('us', 'unknown')
  AND NOT j.sponsorship_block
  AND j.employment_type IN ('full_time', 'unknown')
  AND j.company NOT IN (SELECT slug FROM company_blocklist)
ORDER BY j.first_seen_at DESC
"""

_WORKDAY_HOST = re.compile(r"\.wd\d+\.myworkdayjobs\.com$", re.IGNORECASE)
_ACRONYMS = {"ai": "AI", "aws": "AWS", "usa": "USA", "us": "US", "ibm": "IBM", "nfl": "NFL", "nvidia": "NVIDIA", "sre": "SRE", "ui": "UI", "it": "IT"}


def prettify_slug(slug: str | None) -> str:
    """Turn a source slug into a readable fallback without exposing Workday hosts."""
    value = (slug or "").strip()
    parts = [part.strip() for part in value.split("|") if part.strip()]
    if parts:
        # Workday's persisted company key is host|tenant|site; display the tenant.
        value = parts[1] if len(parts) > 1 and _WORKDAY_HOST.search(parts[0]) else parts[-1]
    value = value.rsplit("/", 1)[-1]
    value = _WORKDAY_HOST.sub("", value)
    value = re.sub(r"\.(com|io|ai|net|org)$", "", value, flags=re.IGNORECASE)
    words = [word for word in re.split(r"[-_.\s]+", value) if word]
    return " ".join(_ACRONYMS.get(word.casefold(), word[:1].upper() + word[1:]) for word in words) or "Unknown company"


def resolve_display_name(company_display: str | None, registry_name: str | None, company_slug: str | None) -> str:
    """Apply the feed's display-name precedence: board, registry, prettified slug."""
    for candidate in (company_display, registry_name):
        if candidate and candidate.strip():
            clean = candidate.strip()
            if _WORKDAY_HOST.search(clean) or ("|" in clean and ".myworkdayjobs.com" in clean.casefold()):
                return prettify_slug(clean)
            return clean
    return prettify_slug(company_slug)


def _time_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    raise TypeError(f"expected datetime, got {type(value).__name__}")


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("company") or "").casefold(), str(row.get("title") or "").casefold(), str(row.get("content_hash") or ""))


def collapse_duplicates(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-company/title/content rows; retain the earliest link and all locations."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for source in rows:
        row = dict(source)
        # A missing content hash is not identity evidence: keep each posting separate.
        key = _identity(row) if row.get("content_hash") else (str(row.get("company") or "").casefold(), str(row.get("title") or "").casefold(), f"__row_{len(groups)}_{row.get('id')}__")
        groups.setdefault(key, []).append(row)

    collapsed: list[dict[str, Any]] = []
    for members in groups.values():
        members.sort(key=lambda item: (_time_value(item["first_seen_at"]), str(item.get("id") or "")))
        chosen = members[0].copy()
        locations: list[str] = []
        for item in members:
            location = (item.get("location") or "").strip()
            if location and location not in locations:
                locations.append(location)
        chosen["locations"] = locations
        chosen["location_count"] = len(locations)
        chosen["has_unknown_location"] = any(item.get("location_class") == "unknown" for item in members)
        chosen["duplicate_count"] = len(members)
        collapsed.append(chosen)
    return sorted(collapsed, key=lambda item: _time_value(item["first_seen_at"]), reverse=True)


def _is_new(first_seen_at: Any, last_generated_at: datetime | None) -> bool:
    if last_generated_at is None:
        return True
    return _time_value(first_seen_at) > _time_value(last_generated_at)


def relative_age(then: Any, now: datetime) -> str:
    seconds = max(0, int((_time_value(now) - _time_value(then)).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def experience_label(row: Mapping[str, Any]) -> str:
    if row.get("is_new_grad_title") is True:
        return "New grad"
    years = row.get("min_years_required")
    if years is None:
        return "Not stated"
    try:
        return "0-2 yrs" if float(years) <= 2 else "3+ yrs"
    except (TypeError, ValueError):
        return "Not stated"


def filter_reasons(row: Mapping[str, Any], *, now: datetime, days: int = 7) -> list[str]:
    """Explain which Phase 3 query predicates reject a matched database row."""
    reasons: list[str] = []
    if row.get("expired_at") is not None:
        reasons.append("expired")
    if row.get("is_tech_title") is not True:
        reasons.append("not_tech_title")
    if row.get("is_senior_title") is not False:
        reasons.append("senior_or_unclassified")
    if row.get("location_class") not in {"us", "unknown"}:
        reasons.append("location_class_not_us_or_unknown")
    if row.get("sponsorship_block") is not False:
        reasons.append("sponsorship_block_or_unclassified")
    if row.get("employment_type") not in {"full_time", "unknown"}:
        reasons.append("employment_type_not_full_time_or_unknown")
    if row.get("blocklisted") is True:
        reasons.append("company_blocklisted")
    if row.get("first_seen_at") is None or (_time_value(now) - _time_value(row["first_seen_at"])).total_seconds() > days * 86400:
        reasons.append("outside_date_window")
    return reasons


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return escape(value.strip(), quote=True)


def render_html(
    rows: Iterable[Mapping[str, Any]], *, generated_at: datetime,
    last_generated_at: datetime | None = None, days: int = 7,
) -> str:
    """Render feed rows into a single offline-friendly HTML document."""
    jobs = collapse_duplicates(rows)
    groups: dict[date, list[dict[str, Any]]] = {}
    for job in jobs:
        groups.setdefault(_time_value(job["first_seen_at"]).date(), []).append(job)

    sections: list[str] = []
    for day in sorted(groups, reverse=True):
        cards: list[str] = []
        for job in groups[day]:
            name = escape(resolve_display_name(job.get("company_display"), job.get("registry_name"), job.get("company")))
            title = escape(str(job.get("title") or "Untitled role"))
            url = _safe_url(job.get("application_url"))
            linked_title = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
            locations = job.get("locations") or ([job["location"]] if job.get("location") else [])
            location_text = escape(str(locations[0])) if locations else "Location not stated"
            if job.get("has_unknown_location", job.get("location_class") == "unknown"):
                location_text += ' <span class="unknown" title="Location is not fully verified">⚠ Unknown</span>'
            extra_locations = max(0, int(job.get("location_count", len(locations))) - 1)
            if extra_locations:
                location_text += f' <span class="location-count">+{extra_locations} locations</span>'
            new_marker = ' <span class="new">NEW</span>' if _is_new(job["first_seen_at"], last_generated_at) else ""
            source = escape(str(job.get("ats") or job.get("source") or "Unknown ATS"))
            age = relative_age(job["first_seen_at"], generated_at)
            cards.append(
                '<article class="job">'
                f'<div class="job-head"><div class="role">{linked_title}{new_marker}</div>'
                f'<div class="company">{name}</div></div>'
                f'<div class="details"><span>{location_text}</span>'
                f'<span class="experience">{escape(experience_label(job))}</span>'
                f'<span class="source">{source}</span><time>{escape(age)}</time></div></article>'
            )
        sections.append(f'<section><h2>{day.isoformat()}</h2>{"".join(cards)}</section>')

    body = "".join(sections) or '<p class="empty">No matching jobs found in this window.</p>'
    stamp = _time_value(generated_at).strftime("%Y-%m-%d %H:%M UTC")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CareerOS Daily Job Feed</title><style>
:root{{color-scheme:light dark;--bg:#0b1020;--card:#151d30;--line:#2c3851;--text:#edf2fc;--muted:#aebbd1;--link:#8ab4ff;--accent:#b6f09c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:920px;margin:auto;padding:24px 16px 48px}}header{{margin-bottom:24px}}h1{{font-size:1.65rem;margin:0 0 4px}}.stamp,.summary{{color:var(--muted);font-size:.9rem}}section{{margin:24px 0}}h2{{font-size:1rem;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:7px}}
.job{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}}.job-head{{display:flex;justify-content:space-between;gap:14px;align-items:baseline}}.role{{font-weight:650;font-size:1.03rem}}a{{color:var(--link);text-decoration-thickness:1px;text-underline-offset:3px}}.company{{font-weight:600;white-space:nowrap}}.details{{display:flex;flex-wrap:wrap;gap:8px 16px;color:var(--muted);font-size:.88rem;margin-top:8px}}.experience{{color:var(--text)}}.unknown{{color:#ffd479;font-weight:650}}.location-count{{color:var(--muted)}}.new{{display:inline-block;border:1px solid #54863c;border-radius:99px;padding:1px 7px;color:var(--accent);font-size:.68rem;letter-spacing:.04em;vertical-align:middle}}.empty{{padding:28px;color:var(--muted)}}
@media(max-width:560px){{main{{padding:18px 12px 36px}}.job{{padding:13px}}.job-head{{display:block}}.company{{margin-top:3px}}.details{{gap:6px 12px}}}}
</style></head><body><main><header><h1>CareerOS Daily Job Feed</h1><div class="summary">Showing eligible classified jobs first seen in the last {int(days)} days.</div><div class="stamp">Generated {escape(stamp)} · {len(jobs)} postings</div></header>{body}</main></body></html>'''


def load_state(path: Path) -> datetime | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("last_generated_at")
    return _time_value(value) if value else None


def write_state(path: Path, generated_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"last_generated_at": _time_value(generated_at).isoformat()}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "feed.html")
    parser.add_argument("--state-file", type=Path, default=ROOT / "reports" / "feed.state.json")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")

    from sqlalchemy import text
    from app.database import SessionLocal

    generated_at = datetime.now(timezone.utc)
    previous_run = load_state(args.state_file)
    db = SessionLocal()
    try:
        rows = db.execute(text(FEED_SQL), {"days": args.days}).mappings().all()
    finally:
        db.close()
    html = render_html(rows, generated_at=generated_at, last_generated_at=previous_run, days=args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(args.output)
    write_state(args.state_file, generated_at)
    print(f"wrote {args.output} ({len(collapse_duplicates(rows))} postings)")


if __name__ == "__main__":
    main()
