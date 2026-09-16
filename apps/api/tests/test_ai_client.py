from app.services.ai_client import (
    expand_provider_order,
    first_numbered_gemini_key,
    numbered_gemini_keys,
)


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


def test_numbered_gemini_keys_return_sorted_pool():
    assert numbered_gemini_keys({"GEMINI_KEY_2": "two", "GEMINI_KEY_1": "one"}) == [
        "one",
        "two",
    ]


def test_expand_provider_order_expands_gemini_pool(monkeypatch):
    from app.services import ai_client

    monkeypatch.setitem(ai_client.ALL_PROVIDERS, "gemini_key_1", {"api_key": "one"})
    monkeypatch.setitem(ai_client.ALL_PROVIDERS, "gemini_key_2", {"api_key": "two"})

    assert expand_provider_order(["groq", "gemini_pool", "gemini"])[:4] == [
        "groq",
        "gemini_key_1",
        "gemini_key_2",
        "gemini",
    ]
