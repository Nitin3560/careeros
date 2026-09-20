from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import re
from typing import Any

from lxml import etree
from lxml import html as lxml_html

from .types import NormalizedJob


BLOCK_TAGS = {"p", "div", "section", "article", "br", "hr", "table", "tr"}
HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
DROP_TAGS = {"script", "style", "noscript", "svg"}
NORMALIZER_VERSION = 2


def _clean_fragment(value: str | None) -> str:
    return html.unescape(value or "").replace("\x00", "")


def _compact(value: str) -> str:
    # ``\s`` includes NBSP and the other Unicode space separators. Normalize
    # them before collapsing so source HTML cannot create invisible artifacts.
    return re.sub(r"\s+", " ", value).strip()


def html_to_text(value: str | None) -> str:
    source = _clean_fragment(value)
    if not source.strip():
        return ""
    try:
        root = lxml_html.fragment_fromstring(source, create_parent="div")
    except (etree.ParserError, ValueError):
        return _compact(re.sub(r"<[^>]+>", " ", source))

    lines: list[str] = []

    def add(text: str = "", blank: bool = False) -> None:
        cleaned = _compact(text)
        if cleaned:
            lines.append(cleaned)
        if blank and lines and lines[-1] != "":
            lines.append("")

    def visible_text(node: etree._Element) -> str:
        return _compact(" ".join(node.itertext()))

    def add_heading_or_paragraph(text: str, *, real_heading: bool = False) -> None:
        if not text:
            return
        words = text.split()
        short_heading = len(text) <= 80 and len(words) <= 12 and not text.endswith(".")
        if (real_heading and len(text) <= 120) or (not real_heading and short_heading):
            add(f"## {text}", blank=True)
        else:
            add(text, blank=True)

    def walk(node: etree._Element) -> None:
        tag = str(node.tag).lower() if isinstance(node.tag, str) else ""
        if tag in DROP_TAGS:
            return
        if tag in HEADING_TAGS:
            add_heading_or_paragraph(visible_text(node), real_heading=True)
            return
        if tag == "li":
            add(f"- {visible_text(node)}")
            return
        if tag in {"p", "div"}:
            children = [child for child in node if isinstance(child.tag, str)]
            strong_only = bool(children) and all(
                str(child.tag).lower() in {"strong", "b", "br"} for child in children
            ) and not _compact(node.text or "")
            text = visible_text(node)
            if strong_only and text:
                add_heading_or_paragraph(text)
                return
            has_block_children = tag == "div" and any(
                str(child.tag).lower() in BLOCK_TAGS | HEADING_TAGS | {"ul", "ol", "li"}
                for child in children
            )
            if text and not has_block_children:
                add(text, blank=True)
                return
        if tag == "br":
            add(blank=True)
            return
        for child in node:
            walk(child)

    for child in root:
        walk(child)
    if not lines:
        add(visible_text(root))

    output = "\n".join(lines)
    output = re.sub(r"\n[ \t]+", "\n", output)
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output.strip()


def source_description_html(source: str, raw: dict[str, Any]) -> str:
    if source == "greenhouse":
        return _clean_fragment(raw.get("content"))
    if source == "ashby":
        return _clean_fragment(raw.get("descriptionHtml") or raw.get("descriptionPlain"))
    if source == "lever":
        parts = [raw.get("description") or raw.get("descriptionPlain")]
        for item in raw.get("lists") or []:
            if item.get("text"):
                parts.append(f"<h3>{html.escape(str(item['text']))}</h3>")
            parts.append(item.get("content"))
        parts.append(raw.get("additional") or raw.get("additionalPlain"))
        return _clean_fragment("\n".join(str(part) for part in parts if part))
    if source == "amazon":
        parts: list[str] = []
        for heading, key in (
            ("Description", "description"),
            ("Basic Qualifications", "basic_qualifications"),
            ("Preferred Qualifications", "preferred_qualifications"),
        ):
            if raw.get(key):
                parts.append(f"<h2>{heading}</h2><p>{raw[key]}</p>")
        return _clean_fragment("\n".join(parts))
    return _clean_fragment(raw.get("descriptionHtml") or raw.get("description") or raw.get("descriptionPlain"))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value)
    for parser in (
        lambda: datetime.fromisoformat(text.replace("Z", "+00:00")),
        lambda: datetime.strptime(text, "%B %d, %Y").replace(tzinfo=timezone.utc),
        lambda: datetime.strptime(text, "%b %d, %Y").replace(tzinfo=timezone.utc),
    ):
        try:
            result = parser()
            if result.tzinfo:
                return result.astimezone(timezone.utc).replace(tzinfo=None)
            return result
        except ValueError:
            pass
    return None


def external_id(source: str, raw: dict[str, Any]) -> str:
    raw_id = raw.get("id_icims") if source == "amazon" else raw.get("id")
    raw_id = raw_id or raw.get("id") or raw.get("jobId")
    return f"{source}_{raw_id}"


def normalize_job(source: str, slug: str, raw: dict[str, Any], *, pending: bool = False) -> NormalizedJob:
    if source == "greenhouse":
        title = raw.get("title") or ""
        location = (raw.get("location") or {}).get("name")
        url = raw.get("absolute_url")
        posted = raw.get("updated_at")
    elif source == "lever":
        title = raw.get("text") or ""
        location = (raw.get("categories") or {}).get("location")
        url = raw.get("hostedUrl") or raw.get("applyUrl")
        posted = raw.get("createdAt")
    elif source == "ashby":
        title = raw.get("title") or ""
        raw_location = raw.get("location")
        location = raw_location if isinstance(raw_location, str) else (raw_location or {}).get("name")
        url = raw.get("jobUrl") or raw.get("applyUrl")
        posted = raw.get("publishedAt")
    else:
        title = raw.get("title") or ""
        location = raw.get("normalized_location") or raw.get("location")
        url = raw.get("url_next_step") or raw.get("job_path")
        if url and str(url).startswith("/"):
            url = f"https://www.amazon.jobs{url}"
        posted = raw.get("posted_date")

    description_html = None if pending else source_description_html(source, raw)
    description_text = "" if pending else html_to_text(description_html)
    digest = hashlib.sha256(
        "|".join((str(title), str(location or ""), description_text)).encode("utf-8")
    ).hexdigest()
    return NormalizedJob(
        external_id=external_id(source, raw),
        source=source,
        company="amazon" if source == "amazon" else slug,
        title=str(title).replace("\x00", ""),
        location=str(location).replace("\x00", "") if location else None,
        description_text=description_text,
        description_html=description_html,
        description_status="pending" if pending else "ok",
        application_url=str(url) if url else None,
        date_posted=_parse_datetime(posted),
        raw_payload=raw,
        content_hash=digest,
    )


def stable_list_hash(source: str, jobs: list[dict[str, Any]]) -> str:
    stable = []
    for job in jobs:
        location = job.get("location")
        if isinstance(location, dict):
            location = location.get("name") or location.get("location")
        stable.append(
            {
                "id": external_id(source, job),
                "title": job.get("title") or job.get("text"),
                "location": location or (job.get("categories") or {}).get("location"),
                "updated": job.get("updated_at") or job.get("publishedAt") or job.get("createdAt"),
            }
        )
    payload = json.dumps(sorted(stable, key=lambda item: item["id"]), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
