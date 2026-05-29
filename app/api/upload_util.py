"""Bounded async read for multipart uploads."""

from __future__ import annotations

from fastapi import UploadFile

from app.domain.errors import UploadError


async def read_upload_bounded(upload: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadError("file_too_large", f"Max upload size is {max_bytes} bytes")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise UploadError("empty_upload", "Upload body is empty — possible interrupted transfer")
    return data
