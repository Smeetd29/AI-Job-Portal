from __future__ import annotations

from pathlib import Path
from rest_framework.exceptions import ValidationError

MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
ALLOWED_MIME_PREFIXES = {"application/pdf", "application/vnd.openxmlformats-officedocument", "application/msword", "text/plain", "application/octet-stream"}

def validate_resume_upload(file_obj) -> None:
    """Validates resume file size, extension, and binary signature.

    Raises rest_framework.exceptions.ValidationError on invalid uploads.
    """
    if not file_obj:
        return

    # 1. Size Validation
    size = getattr(file_obj, "size", 0)
    if size > MAX_RESUME_SIZE_BYTES:
        raise ValidationError(
            f"Uploaded resume exceeds maximum allowed size of 10 MB (File size: {size / (1024 * 1024):.1f} MB)."
        )

    # 2. Extension Validation
    name = getattr(file_obj, "name", "") or ""
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '{suffix}'. Allowed formats: PDF, DOCX, DOC, TXT."
        )

    # 3. Magic Header Validation
    header = b""
    if hasattr(file_obj, "read"):
        header = file_obj.read(16)
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

    if suffix == ".pdf" and not header.startswith(b"%PDF"):
        raise ValidationError("Invalid PDF file: corrupted or invalid file header signature.")
    if suffix == ".docx" and not header.startswith(b"PK\x03\x04"):
        raise ValidationError("Invalid DOCX document: corrupted or invalid ZIP structure.")
