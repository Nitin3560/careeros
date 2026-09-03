import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx


MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = """You extract verifiable facts about a software engineer from a codebase.

Rules:
- Every fact must be supported by source files in the packed repository.
- Documentation is a claim, not proof. If code does not implement it, mark it CONFLICTED or omit it.
- Dependencies, unused config, generated scaffolding, and lockfiles are not facts about what was built.
- Do not invent metrics, dates, scale, ownership, team size, or production claims.
- Output only valid JSON.
"""

PROMPT = """Read this packed repository and emit atomic candidate facts.

Return JSON exactly in this shape:
{"facts":[{"id":"F01","claim":str,"tier":"OBSERVED|DERIVED|CONFLICTED","technologies":[str],"evidence":[str],"note":str}]}

Prefer 25-45 high-signal facts. Include concrete technologies only when code evidence supports them.

<PACKED_REPOSITORY>
{codebase}
</PACKED_REPOSITORY>
"""


def parse_json(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found: {raw[:300]}")
    return json.loads(cleaned[start : end + 1])


def call_gemini(api_key: str, model: str, prompt: str, attempts: int = 4) -> str:
    url = API_URL.format(model=model)
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    last_error = None
    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=180) as client:
                response = client.post(url, params={"key": api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Gemini extraction failed: {last_error}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("packed_repo")
    parser.add_argument("--project", required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set")

    codebase = Path(args.packed_repo).read_text()
    sys.stderr.write(f"{args.project}: packed ~{len(codebase) // 4} tokens\n")
    raw = call_gemini(api_key, args.model, PROMPT.format(codebase=codebase))
    facts = parse_json(raw)
    json.dump(
        {
            "model": args.model,
            "project": args.project,
            "facts": facts.get("facts", []),
        },
        sys.stdout,
        indent=2,
    )


if __name__ == "__main__":
    main()
