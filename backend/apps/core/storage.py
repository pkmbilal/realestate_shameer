"""Direct S3 access for things django-storages doesn't cover (presigned uploads, HEAD)."""

import boto3
from botocore.config import Config
from django.conf import settings


def _options() -> dict:
    return settings.STORAGES["default"]["OPTIONS"]


def bucket_name() -> str:
    return _options()["bucket_name"]


def s3_client(*, public: bool = False):
    """S3 client for the media bucket.

    `public=True` signs URLs for the address browsers use (S3_PUBLIC_ENDPOINT_URL);
    signing never contacts the server, so this works even when that address is only
    reachable from outside Docker.
    """
    options = _options()
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL if public else options["endpoint_url"],
        aws_access_key_id=options["access_key"],
        aws_secret_access_key=options["secret_key"],
        region_name=options["region_name"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
