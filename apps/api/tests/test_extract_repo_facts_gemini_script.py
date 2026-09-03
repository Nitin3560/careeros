import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "extract_repo_facts_gemini.py"
SPEC = importlib.util.spec_from_file_location("extract_repo_facts_gemini_script", SCRIPT_PATH)
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


def test_parse_json_accepts_markdown_fence():
    parsed = extractor.parse_json('```json\n{"facts": [{"id": "F01"}]}\n```')

    assert parsed == {"facts": [{"id": "F01"}]}


def test_prompt_marks_packed_repo_as_data():
    assert "<PACKED_REPOSITORY>" in extractor.PROMPT
    assert "Output only valid JSON" in extractor.SYSTEM


def test_prompt_substitution_keeps_json_schema_literal():
    prompt = extractor.PROMPT.replace("{codebase}", "code")

    assert '{"facts"' in prompt
    assert "code" in prompt
