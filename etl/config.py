"""Központi konfiguráció — minden beállítás környezeti változóból, ésszerű alapértékkel."""
import os

PG = dict(
    host=os.getenv("POSTGRES_HOST", "postgres"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    user=os.getenv("POSTGRES_USER", "dataeng"),
    password=os.getenv("POSTGRES_PASSWORD", "dataeng_pwd"),
    dbname=os.getenv("POSTGRES_DB", "warehouse"),
)

MINIO = dict(
    endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
    bucket=os.getenv("MINIO_BUCKET", "datalake"),
)

INTERVAL = int(os.getenv("ETL_INTERVAL_SECONDS", "20"))
BATCH_SIZE = int(os.getenv("ETL_BATCH_SIZE", "250"))
N_CUSTOMERS = int(os.getenv("ETL_N_CUSTOMERS", "600"))
SEED = int(os.getenv("ETL_SEED", "42"))
