import io
import json
import re

from pypdf import PdfReader

from app.services.ai_client import call_llm


def extract_text(filename: str, file_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if filename.lower().endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type. Please upload a .pdf or .txt file.")


PARSE_SYSTEM_PROMPT = """You extract structured candidate data from resume text.

Rules:
- Only extract what is explicitly stated in the resume. Never invent, infer, or embellish.
- For each skill, include supporting evidence (a project, role, or achievement that demonstrates it) if present in the text.
- Respond with ONLY valid JSON, no markdown formatting, no extra text.

Output this exact JSON shape:
{
  "full_name": <string or null>,
  "skills": [{"name": <string>, "evidence": [<short strings>]}],
  "experience": [{"title": <string>, "company": <string>, "duration": <string>, "highlights": [<short strings>]}],
  "education": [{"degree": <string>, "institution": <string>, "year": <string or null>}],
  "preferred_roles": [<inferred job titles this person is likely targeting, based on their experience>]
}"""


def parse_resume_to_profile(resume_text: str) -> dict:
    truncated = resume_text[:6000]
    try:
        raw_output = call_llm(
            PARSE_SYSTEM_PROMPT,
            f"RESUME TEXT:\n{truncated}",
            provider_order=["groq", "gemini"],
            max_tokens=1500,
            max_retries=1,
        )
    except Exception as exc:
        return _fallback_profile(
            resume_text,
            "AI parsing is temporarily unavailable. Basic extraction was used.",
        )

    cleaned_output = _clean_json_output(raw_output)

    try:
        return json.loads(cleaned_output)
    except json.JSONDecodeError:
        profile = _fallback_profile(resume_text, "AI returned malformed JSON")
        profile["raw_output"] = raw_output
        return profile


def _clean_json_output(raw_output: str) -> str:
    cleaned = raw_output.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and start < end:
        return cleaned[start : end + 1]

    return cleaned


def _fallback_profile(resume_text: str, warning: str) -> dict:
    return {
        "full_name": _guess_full_name(resume_text),
        "skills": _extract_known_skills(resume_text),
        "experience": [],
        "education": [],
        "preferred_roles": _guess_preferred_roles(resume_text),
        "parse_warning": warning,
    }


def _guess_full_name(resume_text: str) -> str | None:
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if not cleaned or "@" in cleaned or len(cleaned.split()) > 5:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", cleaned):
            return cleaned
    return None


def _extract_known_skills(resume_text: str) -> list[dict]:
    known_skills = [
        "Python",
        "C++",
        "C",
        "JavaScript",
        "TypeScript",
        "SQL",
        "PostgreSQL",
        "Docker",
        "FastAPI",
        "React",
        "Next.js",
        "ROS2",
        "PyBullet",
        "Gazebo",
        "PX4",
        "RLlib",
        "CTDE-MAPPO",
        "Multi-Agent Reinforcement Learning",
        "Git",
    ]
    found = []
    lower_text = resume_text.lower()
    for skill in known_skills:
        if skill.lower() in lower_text:
            found.append({"name": skill, "evidence": []})
    return found


def _guess_preferred_roles(resume_text: str) -> list[str]:
    lower_text = resume_text.lower()
    roles = []
    if any(term in lower_text for term in ["ros2", "pybullet", "gazebo", "px4"]):
        roles.append("Autonomous Systems Engineer")
    if any(term in lower_text for term in ["python", "c++", "fastapi", "sql"]):
        roles.append("Software Developer")
    if "research" in lower_text or "reinforcement learning" in lower_text:
        roles.append("Researcher")
    return roles or ["Software Developer"]
