from app.services.ai_client import first_numbered_gemini_key


def test_first_numbered_gemini_key_uses_lowest_numbered_key():
    assert (
        first_numbered_gemini_key(
            {
                "GEMINI_KEY_4": "four",
                "GEMINI_KEY_1": "one",
                "GEMINI_KEY_bad": "bad",
                "GEMINI_API_KEY": "ignored",
            }
        )
        == "one"
    )
