import importlib


def test_allowed_origins_come_from_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com, http://localhost:3000")

    from app import main

    reloaded = importlib.reload(main)

    assert reloaded.allowed_origins == [
        "https://app.example.com",
        "http://localhost:3000",
    ]
