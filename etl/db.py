"""PostgreSQL segédfüggvények — robusztus, retry-os kapcsolódással."""
import time
import logging

import psycopg2

import config

log = logging.getLogger("etl.db")


def connect(retries: int = 40, delay: float = 3.0):
    """Kapcsolódás a Postgreshez, exponenciális helyett fix backoffal.

    Az ETL akkor is túléli, ha a DB pár másodperccel később áll fel.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(**config.PG, connect_timeout=5)
            conn.autocommit = False
            log.info("PostgreSQL kapcsolat létrejött (%s:%s/%s)",
                     config.PG["host"], config.PG["port"], config.PG["dbname"])
            return conn
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log.warning("Postgres még nem elérhető (%d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Nem sikerült kapcsolódni a Postgreshez: {last_err}")


def run_sql_file(conn, path: str) -> None:
    """Egy teljes .sql fájl lefuttatása (több utasítás is lehet benne)."""
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    log.info("SQL fájl alkalmazva: %s", path)
