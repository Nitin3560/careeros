from app.services.auth import hash_password, verify_password


def test_hash_password_verifies_only_correct_password():
    password_hash = hash_password("correct-password")

    assert password_hash != "correct-password"
    assert verify_password("correct-password", password_hash)
    assert not verify_password("wrong-password", password_hash)
