from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app import models


class GreenhouseFillHalt(RuntimeError):
    """Raised when a packet/form cannot be filled safely."""


@dataclass(frozen=True)
class FillValue:
    value: str
    kind: str = "text"


IDENTITY_KEYS = {"full_name", "email", "phone", "linkedin", "github", "portfolio"}
YES_VALUES = {"yes", "true", "1"}
NO_VALUES = {"no", "false", "0"}


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _truthy(value: object) -> bool:
    return _norm(value) in YES_VALUES


def _falsey(value: object) -> bool:
    return _norm(value) in NO_VALUES


def _fact_map(facts: list[models.CandidateFact]) -> dict[str, str]:
    return {fact.fact_key: fact.fact_value for fact in facts if fact.fact_value}


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) < 2:
        raise GreenhouseFillHalt("full_name must include first and last name")
    return parts[0], " ".join(parts[1:])


def is_greenhouse_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return host.endswith("greenhouse.io") or host.endswith("greenhouse.io:443")


def load_ready_packet(db: Session, packet_id: str | None = None, job_id: str | None = None, profile_version: int = 1):
    query = db.query(models.ApplicationPacket)
    if packet_id:
        query = query.filter(models.ApplicationPacket.id == uuid.UUID(str(packet_id)))
    elif job_id:
        query = query.filter(
            models.ApplicationPacket.job_id == uuid.UUID(str(job_id)),
            models.ApplicationPacket.profile_version == profile_version,
        )
    else:
        raise GreenhouseFillHalt("packet_id or job_id is required")
    packet = query.first()
    if not packet:
        raise GreenhouseFillHalt("application packet not found")
    if packet.status != "ready":
        raise GreenhouseFillHalt(f"packet must be ready; got {packet.status}: {packet.blocked_reason}")
    job = db.query(models.Job).filter(models.Job.id == packet.job_id).one()
    facts = []
    if packet.fact_ids:
        facts = db.query(models.CandidateFact).filter(models.CandidateFact.id.in_(packet.fact_ids)).all()
    return packet, job, facts


def validate_before_typing(packet: models.ApplicationPacket, job: models.Job, facts: list[models.CandidateFact]) -> dict[str, str]:
    values = _fact_map(facts)
    missing = sorted(IDENTITY_KEYS - set(values))
    if missing:
        raise GreenhouseFillHalt(f"missing identity facts: {', '.join(missing)}")
    if not is_greenhouse_url(job.application_url):
        raise GreenhouseFillHalt(f"not a Greenhouse URL: {job.application_url}")
    if values.get("full_name") != "Nitin Singh Rathore":
        raise GreenhouseFillHalt("full_name does not match attested identity")
    if values.get("email") != "nxr3560@mavs.uta.edu":
        raise GreenhouseFillHalt("email does not match attested identity")
    if not _truthy(values.get("requires_sponsorship")):
        raise GreenhouseFillHalt("requires_sponsorship must be yes/true")
    if not _falsey(values.get("us_person")):
        raise GreenhouseFillHalt("us_person must be no/false")
    try:
        years = float(values.get("professional_swe_years", ""))
    except ValueError as exc:
        raise GreenhouseFillHalt("professional_swe_years must be numeric") from exc
    if not (1.5 <= years <= 2.0):
        raise GreenhouseFillHalt(f"professional_swe_years must be in the 1.5-2.0 bucket; got {years}")
    if not packet.resume_path or not Path(packet.resume_path).exists():
        raise GreenhouseFillHalt("ready packet is missing resume_path")
    return values


def answer_for_label(label: str, values: dict[str, str], packet: models.ApplicationPacket) -> FillValue | None:
    text = _norm(label)
    first, last = split_name(values["full_name"])
    education = values.get("education", "")
    if "first name" in text:
        return FillValue(first)
    if "last name" in text:
        return FillValue(last)
    if text in {"name", "full name"} or "legal name" in text:
        return FillValue(values["full_name"])
    if "email" in text:
        return FillValue(values["email"])
    if "phone" in text:
        return FillValue(values["phone"])
    if text == "country" or text.startswith("country ") or "phone country" in text:
        return FillValue("United States")
    if "location" in text:
        return FillValue(values.get("current_location", "Arlington, TX"))
    if "linkedin" in text:
        return FillValue(values["linkedin"])
    if "github" in text:
        return FillValue(values["github"])
    if "website" in text or "portfolio" in text:
        return FillValue(values["portfolio"])
    if "resume" in text or "cv" in text:
        return FillValue(str(packet.resume_path), "file")
    if "cover letter" in text:
        return FillValue(packet.cover_letter, "textarea") if packet.cover_letter else None
    if "authorized" in text and ("united states" in text or "u.s." in text or "us" in text):
        return FillValue("Yes")
    if "sponsor" in text or "sponsorship" in text or "visa" in text:
        return FillValue("Yes" if _truthy(values.get("requires_sponsorship")) else "No")
    if "u.s. person" in text or "us person" in text:
        return FillValue("No" if _falsey(values.get("us_person")) else "Yes")
    if "years" in text and "experience" in text:
        return FillValue(values["professional_swe_years"])
    if "how did you hear about this job" in text:
        return FillValue("Company website")
    if "school" in text:
        return FillValue("University of Texas at Arlington")
    if "degree" in text:
        return FillValue("Master's Degree")
    if "discipline" in text:
        return FillValue("Computer Science")
    if "current or previous spacex" in text or "previously worked at spacex" in text:
        return FillValue("No")
    if "are you legally authorized" in text and "united states" in text:
        return FillValue("Yes")
    if "at least 18 years" in text:
        return FillValue("Yes")
    if "gender" in text or "race" in text or "ethnicity" in text or "veteran" in text or "disability" in text:
        return FillValue("I don't wish to answer")
    return None


def validate_immovable_question(label: str, answer: str, values: dict[str, str]) -> None:
    text = _norm(label)
    ans = _norm(answer)
    if "sponsor" in text or "sponsorship" in text or "visa" in text:
        if _truthy(values.get("requires_sponsorship")) and ans not in YES_VALUES:
            raise GreenhouseFillHalt("validator mismatch: sponsorship answer must be Yes")
    if "u.s. person" in text or "us person" in text:
        if _falsey(values.get("us_person")) and ans not in NO_VALUES:
            raise GreenhouseFillHalt("validator mismatch: us_person answer must be No")
    if "email" in text and answer != values.get("email"):
        raise GreenhouseFillHalt("validator mismatch: email answer changed")
    if (text in {"name", "full name"} or "legal name" in text) and answer != values.get("full_name"):
        raise GreenhouseFillHalt("validator mismatch: full_name answer changed")


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_")[:80] or "greenhouse"


def _field_label(field) -> str:
    return field.evaluate(
        """el => {
            const pieces = [];
            const add = value => { if (value && !pieces.includes(value.trim())) pieces.push(value.trim()); };
            add(el.getAttribute('aria-label'));
            add(el.getAttribute('placeholder'));
            add(el.getAttribute('name'));
            add(el.getAttribute('id'));
            if (el.id) {
                const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                if (label) add(label.innerText);
            }
            const wrapper = el.closest('label, .field, .application-question, .select, .select__container, div');
            if (wrapper) {
                const label = wrapper.querySelector('label');
                if (label) add(label.innerText);
            }
            return pieces.join(' ');
        }"""
    )


def run_greenhouse_dry_run(
    db: Session,
    packet_id: str | None = None,
    job_id: str | None = None,
    profile_version: int = 1,
    output_dir: Path | str = "generated/greenhouse_dry_runs",
    submit: bool = False,
) -> dict:
    if submit:
        raise GreenhouseFillHalt("submit=true is disabled until dry runs are manually reviewed")
    packet, job, facts = load_ready_packet(db, packet_id=packet_id, job_id=job_id, profile_version=profile_version)
    values = validate_before_typing(packet, job, facts)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise GreenhouseFillHalt("Playwright is required for browser filling. Install it and run `playwright install chromium`.") from exc

    run_dir = Path(output_dir) / f"{_safe_name(str(packet.id))}_{_safe_name(job.company)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshots: list[str] = []
    filled: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(job.application_url, wait_until="domcontentloaded")
        screenshots.append(str(run_dir / "00_loaded.png"))
        page.screenshot(path=screenshots[-1], full_page=True)

        fields = page.locator("input, textarea, select").all()
        for index, field in enumerate(fields, start=1):
            if not field.is_visible() or field.is_disabled():
                continue
            if field.get_attribute("aria-hidden") == "true":
                continue
            label = _field_label(field)
            input_type = (field.get_attribute("type") or "").lower()
            required = field.get_attribute("required") is not None or field.get_attribute("aria-required") == "true"
            answer = answer_for_label(label, values, packet)
            if answer is None:
                if required:
                    raise GreenhouseFillHalt(f"required field has no safe answer: {label or input_type or index}")
                continue
            validate_immovable_question(label, answer.value, values)
            tag = field.evaluate("el => el.tagName.toLowerCase()")
            if answer.kind == "file" or input_type == "file":
                field.set_input_files(answer.value)
            elif input_type in {"checkbox", "radio"}:
                if _norm(answer.value) in YES_VALUES:
                    field.check()
            elif tag == "select":
                field.select_option(label=answer.value)
            else:
                field.fill(answer.value)
            filled.append({"label": label, "kind": answer.kind, "value": "<file>" if answer.kind == "file" else answer.value})
            screenshots.append(str(run_dir / f"{index:02d}_{_safe_name(label or input_type)}.png"))
            page.screenshot(path=screenshots[-1], full_page=True)

        submit_buttons = page.locator("button[type=submit], input[type=submit]").count()
        screenshots.append(str(run_dir / "99_final_dry_run_no_submit.png"))
        page.screenshot(path=screenshots[-1], full_page=True)
        browser.close()

    return {
        "packet_id": str(packet.id),
        "job_id": str(job.id),
        "application_url": job.application_url,
        "dry_run": True,
        "submit_buttons_seen": submit_buttons,
        "filled": filled,
        "screenshots": screenshots,
    }
