import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )


def ensure_bucket() -> None:
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        logger.info("Bucket exists: %s", settings.s3_bucket)
    except ClientError:
        logger.info("Creating bucket: %s", settings.s3_bucket)
        client.create_bucket(Bucket=settings.s3_bucket)
    except EndpointConnectionError:
        logger.warning("MinIO not available; skipping bucket creation")


def upload_fileobj(data: bytes, object_key: str) -> str:
    client = _get_client()
    client.put_object(Bucket=settings.s3_bucket, Key=object_key, Body=data)
    logger.info("Uploaded s3://%s/%s", settings.s3_bucket, object_key)
    return object_key


def download_to_temp(object_key: str) -> str:
    client = _get_client()
    suffix = Path(object_key).suffix or ".csv"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        client.download_file(
            Bucket=settings.s3_bucket,
            Key=object_key,
            Filename=path,
        )
        logger.info("Downloaded s3://%s/%s to %s", settings.s3_bucket, object_key, path)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)
    return path


def delete_object(object_key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=object_key)
    logger.info("Deleted s3://%s/%s", settings.s3_bucket, object_key)
