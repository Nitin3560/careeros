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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

import test_evidence_matcher as matcher  # noqa: E402
from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
DEFAULT_OUT = "adjudicator_experiment.json"
KEY_DELAY_SECONDS = 6.0
CALL_TIMEOUT = httpx.Timeout(25.0, connect=10.0, read=15.0, write=10.0, pool=10.0)

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


class KeyScheduler:
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.next_available = [0.0 for _ in keys]
        self.index = 0

    def take(self) -> str:
        index = self.index
        self.index = (self.index + 1) % len(self.keys)
        wait = self.next_available[index] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.next_available[index] = time.monotonic() + KEY_DELAY_SECONDS
        return self.keys[index]


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


def preselection_score(requirement: str, facts: list[dict]) -> tuple[int, int]:
    selected = preselect_facts(requirement, facts, limit=10)
    if not selected:
        return (0, 0)
    selected_ids = {item["id"] for item in selected}
    req_terms = tokens(requirement)
    best_overlap = 0
    best_weight = 0
    for fact in facts:
        if fact["id"] not in selected_ids:
            continue
        overlap = len(req_terms & fact["terms"])
        best_overlap = max(best_overlap, overlap)
        best_weight = max(best_weight, fact["weight"])
    return (best_overlap, best_weight)


def call_gemini(scheduler: KeyScheduler, requirement: str, facts: list[dict]) -> dict:
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
    for attempt in range(2):
        try:
            api_key = scheduler.take()
            response = httpx.post(API, params={"key": api_key}, json=payload, timeout=CALL_TIMEOUT)
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"http {response.status_code}"
                time.sleep((attempt + 1) * 3)
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
    parser.add_argument("--max-requirements", type=int, default=50)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    keys = load_api_keys()
    if not keys:
        raise SystemExit("no Gemini API keys set")
    scheduler = KeyScheduler(keys)

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
    pending = []
    totals = {
        "jobs": 0,
        "skip_hard_jobs": 0,
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
            totals["skip_hard_jobs"] += 1
            continue

        for requirement in deterministic.missing:
            selected = preselect_facts(requirement, facts)
            if selected:
                pending.append(
                    {
                        "item": item,
                        "deterministic": deterministic,
                        "requirement": requirement,
                        "facts": selected,
                        "score": preselection_score(requirement, facts),
                    }
                )

    pending.sort(key=lambda item: item["score"], reverse=True)
    pending = pending[: args.max_requirements]

    grouped = {}
    for index, item in enumerate(pending, start=1):
        job_id = item["item"]["job_id"]
        if job_id not in grouped:
            grouped[job_id] = {
                "item": item["item"],
                "deterministic": item["deterministic"],
                "adjudications": [],
            }

        print(
            f"[{index}/{len(pending)}] {item['item']['company']} | "
            f"{item['requirement'][:80]}",
            flush=True,
        )
        run1 = call_gemini(scheduler, item["requirement"], item["facts"])
        run2 = call_gemini(scheduler, item["requirement"], item["facts"])
        consistent = run1["verdict"] == run2["verdict"]
        totals["requirements_adjudicated"] += 1
        totals["consistent"] += int(consistent)
        totals[run1["verdict"].lower()] += 1
        grouped[job_id]["adjudications"].append(
            {
                "requirement": item["requirement"],
                "facts": item["facts"],
                "run1": run1,
                "run2": run2,
                "consistent": consistent,
            }
            )

    for data in grouped.values():
        item = data["item"]
        deterministic = data["deterministic"]
        adjudications = data["adjudications"]
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
        "max_requirements": args.max_requirements,
        "keys_used": len(keys),
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


def load_api_keys() -> list[str]:
    keys = []
    combined = os.getenv("GEMINI_API_KEYS")
    if combined:
        keys.extend(key.strip() for key in combined.split(",") if key.strip())
    for index in range(1, 6):
        key = os.getenv(f"GEMINI_KEY_{index}")
        if key:
            keys.append(key)
    fallback = os.getenv("GEMINI_API_KEY")
    if fallback:
        keys.append(fallback)
    deduped = []
    for key in keys:
        if key not in deduped:
            deduped.append(key)
    return deduped


if __name__ == "__main__":
    main()
