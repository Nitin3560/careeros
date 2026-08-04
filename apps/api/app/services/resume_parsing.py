import io
import json

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
    raw_output = call_llm(
        PARSE_SYSTEM_PROMPT,
        f"RESUME TEXT:\n{truncated}",
        max_tokens=1500,
        max_retries=5,
    )

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "full_name": None,
            "skills": [],
            "experience": [],
            "education": [],
            "preferred_roles": [],
            "error": "Failed to parse model output",
            "raw_output": raw_output,
        }
