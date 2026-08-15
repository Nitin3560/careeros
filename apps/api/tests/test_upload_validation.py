import pytest

from app.services.upload_validation import MAX_RESUME_BYTES, validate_resume_upload


def test_validate_resume_upload_accepts_txt_file():
    validate_resume_upload("resume.txt", "text/plain", b"resume")


def test_validate_resume_upload_rejects_unknown_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        validate_resume_upload("resume.exe", "application/octet-stream", b"resume")


def test_validate_resume_upload_rejects_wrong_content_type():
    with pytest.raises(ValueError, match="Unsupported file type"):
        validate_resume_upload("resume.pdf", "image/png", b"resume")


def test_validate_resume_upload_rejects_large_file():
    with pytest.raises(ValueError, match="5 MB"):
        validate_resume_upload(
            "resume.txt",
            "text/plain",
            b"x" * (MAX_RESUME_BYTES + 1),
        )
