from pathlib import Path

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/octet-stream",
}
MAX_RESUME_BYTES = 5 * 1024 * 1024


def validate_resume_upload(
    filename: str | None,
    content_type: str | None,
    file_bytes: bytes,
) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_RESUME_EXTENSIONS:
        raise ValueError("Unsupported file type. Please upload a .pdf or .txt file.")

    if content_type and content_type not in ALLOWED_RESUME_CONTENT_TYPES:
        raise ValueError("Unsupported file type. Please upload a .pdf or .txt file.")

    if len(file_bytes) > MAX_RESUME_BYTES:
        raise ValueError("Resume file must be 5 MB or smaller.")
