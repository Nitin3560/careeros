import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402

EARLY_CAREER_RE = re.compile(
    r"\b(new grad|new graduate|early career|university grad|graduate|entry level|entry|junior|intern)\b",
    re.I,
)
SDE_I_II_RE = re.compile(
    r"\b(sde\s*(i|1|ii|2)\b|software development engineer\s*(i|1|ii|2)?\b|"
    r"software engineer\s*(i|1|ii|2)?\b|software developer\s*(i|1|ii|2)?\b)",
    re.I,
)
SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|architect|director|head of|vp)\b",
    re.I,
)
DEFENSE_RE = re.compile(
    r"\b(itar|u\.s\. person|us person|security clearance|clearance|top secret|ts/sci|"
    r"defense|missile|payload|classified|spacecraft|satellite|leo|radar|ew)\b",
    re.I,
)
DEFENSE_COMPANY_RE = re.compile(
    r"\b(anduril|spacex|rocketlab|trueanomaly|varda|archer|cesium|morse|questdefense|"
    r"darkwolf|accenturefederal|freedomconsulting|systemstechnologyresearch|metrostarsystems|"
    r"grvty|muonspace|rebuildmanufacturing)\b",
    re.I,
)
OUTREACH_COMPANY_RE = re.compile(
    r"\b(stripe|amazon|reddit|roblox|block|brex|pinterest|coinbase|gitlab|waymo|"
    r"abnormalsecurity|elastic|clear|idme|lightningai|rdccareers|zoominfo|axon)\b",
    re.I,
)
REMOTE_US_RE = re.compile(r"\b(remote.*(us|usa|united states)|us[- ]remote)\b", re.I)


@dataclass(frozen=True)
class QueueItem:
    queue_key: str
    company: str
    title: str
    location: str | None
    date_posted: datetime | None
    first_seen_at: datetime
    application_url: str | None
    source: str


def as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def action_score(item: QueueItem, now: datetime | None = None) -> tuple[int, list[str]]:
    now = as_aware(now or datetime.now(timezone.utc))
    first_seen_at = as_aware(item.first_seen_at)
    text_blob = " ".join(
        part for part in [item.company, item.title, item.location or ""] if part
    )
    score = 0
    reasons: list[str] = []

    if EARLY_CAREER_RE.search(item.title):
        score += 55
        reasons.append("early-career")
    if SDE_I_II_RE.search(item.title):
        score += 35
        reasons.append("sde-i-ii")
    if not SENIOR_RE.search(item.title):
        score += 18
        reasons.append("not-senior")
    else:
        score -= 30
        reasons.append("senior-or-lead")

    age_hours = max((now - first_seen_at).total_seconds() / 3600, 0)
    if age_hours <= 2:
        score += 30
        reasons.append("fresh<=2h")
    elif age_hours <= 24:
        score += 20
        reasons.append("fresh<=24h")
    elif age_hours <= 72:
        score += 10
        reasons.append("fresh<=72h")

    if item.date_posted:
        posted_age_days = max((now - as_aware(item.date_posted)).days, 0)
        if posted_age_days <= 1:
            score += 15
            reasons.append("posted<=1d")
        elif posted_age_days <= 7:
            score += 8
            reasons.append("posted<=7d")
        elif posted_age_days > 30:
            score -= 20
            reasons.append("old-posting")

    if REMOTE_US_RE.search(item.location or ""):
        score += 8
        reasons.append("remote-us")

    if DEFENSE_COMPANY_RE.search(item.company) or DEFENSE_RE.search(text_blob):
        score -= 140
        reasons.append("defense-itar-risk")

    if OUTREACH_COMPANY_RE.search(item.company):
        score += 12
        reasons.append("outreach-worthy-company")

    return score, reasons


def outreach_score(item: QueueItem) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if OUTREACH_COMPANY_RE.search(item.company):
        score += 35
        reasons.append("known-recruiter-market")
    if EARLY_CAREER_RE.search(item.title) or SDE_I_II_RE.search(item.title):
        score += 25
        reasons.append("candidate-fit-title")
    if not SENIOR_RE.search(item.title):
        score += 10
        reasons.append("not-senior")
    if DEFENSE_COMPANY_RE.search(item.company) or DEFENSE_RE.search(
        f"{item.company} {item.title} {item.location or ''}"
    ):
        score -= 100
        reasons.append("defense-itar-risk")
    return score, reasons


def fetch_items(since_hours: int) -> list[QueueItem]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (queue_key)
                       queue_key, company, title, location, date_posted,
                       first_seen_at, application_url, source
                FROM jobs
                WHERE eligible IS true
                  AND first_seen_at > now() - (:hours * interval '1 hour')
                  AND queue_key IS NOT NULL
                ORDER BY queue_key, first_seen_at DESC, date_posted DESC NULLS LAST
                """
            ),
            {"hours": since_hours},
        ).all()
    finally:
        db.close()

    return [QueueItem(*row) for row in rows]


def print_section(name: str, rows: list[tuple[int, QueueItem, list[str]]], limit: int):
    print(f"\n{name}")
    for score, item, reasons in rows[:limit]:
        print(
            "\t".join(
                [
                    str(score),
                    item.company,
                    item.title,
                    item.location or "",
                    item.source,
                    item.first_seen_at.isoformat(),
                    ",".join(reasons),
                    item.application_url or "",
                ]
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=6)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    items = fetch_items(args.since_hours)
    apply_rows = sorted(
        ((score, item, reasons) for item in items for score, reasons in [action_score(item)]),
        key=lambda row: row[0],
        reverse=True,
    )
    outreach_rows = sorted(
        (
            (score, item, reasons)
            for item in items
            for score, reasons in [outreach_score(item)]
            if score > 0
        ),
        key=lambda row: row[0],
        reverse=True,
    )

    print(f"queue_items={len(items)}")
    print_section("apply_now", apply_rows, args.limit)
    print_section("outreach_now", outreach_rows, args.limit)


if __name__ == "__main__":
    main()
