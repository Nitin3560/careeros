import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "refresh_requirement_verification.py"
SPEC = importlib.util.spec_from_file_location("refresh_requirement_verification_script", SCRIPT_PATH)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


def test_refresh_requirements_updates_existing_ambiguous_state():
    requirements = {
        "hard_requirements": [
            {
                "type": "clearance",
                "value": "Secret clearance",
                "source_text": "Eligible to obtain and maintain an active U.S. Secret security clearance",
                "verification_state": "AMBIGUOUS",
                "verification_note": "no mandatory language in snippet",
            }
        ]
    }

    changed = refresh.refresh_requirements(
        requirements,
        "Eligible to obtain and maintain an active U.S. Secret security clearance.",
    )

    assert changed == 1
    assert requirements["hard_requirements"][0]["verification_state"] == "VERIFIED"
