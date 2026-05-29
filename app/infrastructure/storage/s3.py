"""S3-compatible object storage (MinIO in dev). boto3 imported only when uploading."""

from __future__ import annotations

from typing import BinaryIO

from app.config import settings
from app.domain.errors import StorageError
from app.domain.hashing import sha256_bytes


def _client():
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    from botocore.exceptions import ClientError

    client = _client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def put_object(*, key: str, body: bytes, content_type: str) -> str:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        ensure_bucket()
        _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=body, ContentType=content_type)
        return key
    except (ClientError, BotoCoreError, OSError) as e:
        raise StorageError(f"upload failed: {e}") from e


def put_stream(*, key: str, stream: BinaryIO, content_type: str) -> tuple[str, str]:
    data = stream.read()
    digest = sha256_bytes(data)
    put_object(key=key, body=data, content_type=content_type)
    return key, digest


__all__ = ["put_object", "put_stream"]
