import argparse
import copy
import json
import os
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path

import httpx
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

import test_evidence_matcher as matcher  # noqa: E402
from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
DEFAULT_OUT = "adjudicator_experiment.json"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
}

SYSTEM = """You adjudicate one job requirement against preselected candidate facts.

You only answer whether the candidate facts satisfy this one requirement.
Do not decide whether the candidate should apply.
Do not infer clearance, citizenship, sponsorship, years, or authorization.
Return only valid JSON.

Verdicts:
- MET: direct evidence satisfies the requirement.
- PARTIAL: related evidence exists but does not fully satisfy it.
- UNMET: no provided fact satisfies it.

Schema:
{"verdict":"MET|PARTIAL|UNMET","fact_ids":[str],"reason":str}
"""


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", str(value or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def load_fact_rows(db, user_id: str) -> list[dict]:
    rows = (
        db.query(models.CandidateFact)
        .filter(
            models.CandidateFact.user_id == user_id,
            models.CandidateFact.tier != "ATTESTED",
        )
        .all()
    )
    return [
        {
            "id": str(row.id),
            "key": row.fact_key,
            "value": row.fact_value,
            "project": row.project,
            "weight": row.project_weight,
            "terms": tokens(f"{row.fact_key} {row.fact_value} {row.project or ''}"),
        }
        for row in rows
    ]


def preselect_facts(requirement: str, facts: list[dict], limit: int = 10) -> list[dict]:
    req_terms = tokens(requirement)
    scored = []
    for fact in facts:
        overlap = len(req_terms & fact["terms"])
        if overlap:
            scored.append((overlap, fact["weight"], fact))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [item[2] for item in scored[:limit]]
    return [
        {
            "id": fact["id"],
            "key": fact["key"],
            "value": fact["value"],
            "project": fact["project"],
            "weight": fact["weight"],
        }
        for fact in selected
    ]


def call_gemini(api_key: str, requirement: str, facts: list[dict]) -> dict:
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "requirement": requirement,
                                "candidate_facts": facts,
                            },
                            indent=2,
                        )
                    }
                ],
            }
        ],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    last_error = None
    for attempt in range(4):
        try:
            response = httpx.post(API, params={"key": api_key}, json=payload, timeout=60)
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"http {response.status_code}"
                time.sleep((attempt + 1) * 5)
                continue
            response.raise_for_status()
            data = response.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw)
            if parsed.get("verdict") not in {"MET", "PARTIAL", "UNMET"}:
                raise ValueError("invalid verdict")
            return {
                "verdict": parsed["verdict"],
                "fact_ids": parsed.get("fact_ids", []),
                "reason": parsed.get("reason", ""),
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(2**attempt)
    return {"verdict": "UNMET", "fact_ids": [], "reason": f"adjudication_failed: {last_error}"}


def apply_met_adjudications(decision: matcher.Decision, adjudications: list[dict]) -> matcher.Decision:
    updated = copy.deepcopy(decision)
    met = {item["requirement"] for item in adjudications if item["run1"]["verdict"] == "MET"}
    if not met:
        return updated
    remaining_missing = []
    for missing in updated.missing:
        if missing in met:
            updated.matched.append(missing)
            updated.matched_weight += 1
            updated.missing_weight = max(0, updated.missing_weight - 1)
        else:
            remaining_missing.append(missing)
    updated.missing = remaining_missing
    if updated.action == "REVIEW" and not updated.unresolved and updated.matched_weight > 0:
        if len(updated.matched) >= len(updated.missing):
            updated.action = "APPLY"
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=matcher.DEFAULT_USER_ID)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set")

    db = SessionLocal()
    try:
        profile = matcher.load_profile(args.user_id)
        attested = matcher.load_attested_facts(db, args.user_id)
        years = matcher.compute_professional_swe_years(db, args.user_id)
        facts = load_fact_rows(db, args.user_id)
        items = matcher.load_db_items(args.limit)
    finally:
        db.close()

    output = []
    totals = {
        "jobs": 0,
        "requirements_adjudicated": 0,
        "consistent": 0,
        "met": 0,
        "partial": 0,
        "unmet": 0,
        "changed_actions": 0,
    }
    for item in items:
        deterministic = matcher.evaluate(
            profile,
            item["requirements"],
            attested=attested,
            years=years,
            job_context=item,
        )
        if deterministic.action == "SKIP_HARD":
            continue

        unresolved = []
        for requirement in deterministic.missing:
            selected = preselect_facts(requirement, facts)
            if selected:
                unresolved.append((requirement, selected))

        adjudications = []
        for requirement, selected in unresolved:
            run1 = call_gemini(api_key, requirement, selected)
            run2 = call_gemini(api_key, requirement, selected)
            consistent = run1["verdict"] == run2["verdict"]
            totals["requirements_adjudicated"] += 1
            totals["consistent"] += int(consistent)
            totals[run1["verdict"].lower()] += 1
            adjudications.append(
                {
                    "requirement": requirement,
                    "facts": selected,
                    "run1": run1,
                    "run2": run2,
                    "consistent": consistent,
                }
            )

        updated = apply_met_adjudications(deterministic, adjudications)
        totals["jobs"] += 1
        totals["changed_actions"] += int(updated.action != deterministic.action)
        output.append(
            {
                "job": {
                    "job_id": item["job_id"],
                    "company": item["company"],
                    "title": item["title"],
                    "location": item["location"],
                },
                "deterministic": asdict(deterministic),
                "with_adjudication": asdict(updated),
                "adjudications": adjudications,
            }
        )

    result = {
        "model": MODEL,
        "limit": args.limit,
        "totals": totals,
        "consistency_rate": (
            totals["consistent"] / totals["requirements_adjudicated"]
            if totals["requirements_adjudicated"]
            else None
        ),
        "results": output,
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
