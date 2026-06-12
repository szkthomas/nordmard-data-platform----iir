"""MinIO (S3-kompatibilis) data lake segédfüggvények — boto3-mal."""
import json
import time
import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

import config

log = logging.getLogger("etl.lake")


def make_client(retries: int = 40, delay: float = 3.0):
    """S3 kliens létrehozása MinIO-hoz, retry-os elérhetőség-ellenőrzéssel."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            client = boto3.client(
                "s3",
                endpoint_url=config.MINIO["endpoint"],
                aws_access_key_id=config.MINIO["access_key"],
                aws_secret_access_key=config.MINIO["secret_key"],
                config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
                region_name="us-east-1",
            )
            client.list_buckets()  # tényleges kapcsolat-ellenőrzés
            log.info("MinIO/S3 kapcsolat létrejött (%s)", config.MINIO["endpoint"])
            return client
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log.warning("MinIO még nem elérhető (%d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Nem sikerült kapcsolódni a MinIO-hoz: {last_err}")


def ensure_bucket(client, bucket: str) -> None:
    """Bucket létrehozása, ha még nem létezik (idempotens)."""
    try:
        client.head_bucket(Bucket=bucket)
        log.info("Bucket már létezik: %s", bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
        log.info("Bucket létrehozva: %s", bucket)


def put_ndjson(client, bucket: str, key: str, records: list) -> str:
    """Rekordok lerakása a data lake-be NDJSON (newline-delimited JSON) formátumban.

    Ez a "bronze" réteg: nyers, sorosított adat, particionált kulcs alatt.
    """
    body = "\n".join(json.dumps(r, default=str) for r in records).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/x-ndjson",
    )
    return key
