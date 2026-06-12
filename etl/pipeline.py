"""NordMart ELT pipeline — medallion architektúra (bronze -> silver -> gold).

Folyamat:
  1) Séma + marts felépítése a Postgresben (idempotens).
  2) Termék/ügyfél törzs feltöltése (dim_product, dim_customer) + bronze snapshot.
  3) Végtelen ciklus:
       - friss rendelés-batch generálása
       - BRONZE: nyers NDJSON a MinIO data lake-be (particionált kulcs)
       - SILVER: betöltés a stg_orders staging táblába
       - GOLD : dim_date frissítés + fact_sales feltöltése (számított metrikák)
       - futási napló (etl_run_log) -> observability
"""
import os
import time
import logging
from datetime import datetime, timezone

from psycopg2.extras import execute_values

import config
import db as dbm
import lake as lakem
import generate as gen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s | %(message)s",
)
log = logging.getLogger("etl.pipeline")

SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")


# --------------------------------------------------------------------------- #
#  GOLD — dimenzió-feltöltők
# --------------------------------------------------------------------------- #
def upsert_products(conn, products: list) -> None:
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO dim_product
                (product_id, product_name, category, brand, unit_cost, list_price)
            VALUES %s
            ON CONFLICT (product_id) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                category     = EXCLUDED.category,
                brand        = EXCLUDED.brand,
                unit_cost    = EXCLUDED.unit_cost,
                list_price   = EXCLUDED.list_price
        """, [(p["product_id"], p["product_name"], p["category"],
               p["brand"], p["unit_cost"], p["list_price"]) for p in products])
    conn.commit()


def upsert_customers(conn, customers: list) -> None:
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO dim_customer
                (customer_id, full_name, email, country, city, segment, signup_date)
            VALUES %s
            ON CONFLICT (customer_id) DO NOTHING
        """, [(c["customer_id"], c["full_name"], c["email"], c["country"],
               c["city"], c["segment"], c["signup_date"]) for c in customers])
    conn.commit()


def ensure_dates(conn, date_set) -> None:
    """A batch-ben előforduló dátumok feltöltése a dim_date dimenzióba."""
    month_names = ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    weekday_names = ["", "Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
    rows = []
    for d in sorted(date_set):
        rows.append((
            int(d.strftime("%Y%m%d")), d, d.year, (d.month - 1) // 3 + 1,
            d.month, month_names[d.month], d.day, d.isoweekday(),
            weekday_names[d.isoweekday()], d.isoweekday() >= 6,
        ))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO dim_date
                (date_key, date, year, quarter, month, month_name,
                 day, weekday, weekday_name, is_weekend)
            VALUES %s
            ON CONFLICT (date_key) DO NOTHING
        """, rows)
    conn.commit()


# --------------------------------------------------------------------------- #
#  SILVER + GOLD — batch betöltés
# --------------------------------------------------------------------------- #
def load_staging(conn, batch: list) -> None:
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO stg_orders
                (order_id, order_ts, customer_id, product_id,
                 quantity, unit_price, discount_pct, channel)
            VALUES %s
            ON CONFLICT (order_id) DO NOTHING
        """, [(r["order_id"], r["order_ts"], r["customer_id"], r["product_id"],
               r["quantity"], r["unit_price"], r["discount_pct"], r["channel"])
              for r in batch])
    conn.commit()


def load_facts(conn, order_ids: list) -> int:
    """Staging -> fact_sales transzformáció (számított pénzügyi metrikákkal)."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fact_sales (
                order_id, order_ts, date_key, customer_id, product_id, channel,
                quantity, unit_price, discount_pct,
                gross_amount, discount_amount, net_amount, margin_amount
            )
            SELECT
                s.order_id,
                s.order_ts,
                to_char(s.order_ts AT TIME ZONE 'UTC', 'YYYYMMDD')::int AS date_key,
                s.customer_id,
                s.product_id,
                s.channel,
                s.quantity,
                s.unit_price,
                s.discount_pct,
                (s.quantity * s.unit_price)                                   AS gross_amount,
                (s.quantity * s.unit_price * s.discount_pct / 100.0)          AS discount_amount,
                (s.quantity * s.unit_price * (1 - s.discount_pct / 100.0))    AS net_amount,
                (s.quantity * (s.unit_price * (1 - s.discount_pct / 100.0)
                               - p.unit_cost))                               AS margin_amount
            FROM stg_orders s
            JOIN dim_product p ON p.product_id = s.product_id
            WHERE s.order_id = ANY(%s)
            ON CONFLICT (order_id) DO NOTHING
        """, (order_ids,))
        loaded = cur.rowcount
    conn.commit()
    return loaded


def log_run(conn, batch_size, rows_bronze, rows_loaded, obj, duration_ms, status) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO etl_run_log
                (batch_size, rows_bronze, rows_loaded, bronze_object, duration_ms, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (batch_size, rows_bronze, rows_loaded, obj, duration_ms, status))
    conn.commit()


# --------------------------------------------------------------------------- #
#  Belépési pont
# --------------------------------------------------------------------------- #
def bootstrap(conn, s3):
    """Egyszeri inicializálás: séma, marts, törzsadat, bronze snapshotok."""
    dbm.run_sql_file(conn, os.path.join(SQL_DIR, "01_schema.sql"))
    dbm.run_sql_file(conn, os.path.join(SQL_DIR, "02_marts.sql"))

    products = gen.build_products()
    customers = gen.build_customers(config.N_CUSTOMERS)
    upsert_products(conn, products)
    upsert_customers(conn, customers)

    lakem.put_ndjson(s3, config.MINIO["bucket"], "raw/master/products.json", products)
    lakem.put_ndjson(s3, config.MINIO["bucket"], "raw/master/customers.json", customers)
    log.info("Törzsadat betöltve: %d termék, %d ügyfél", len(products), len(customers))
    return products


def main():
    log.info("=== NordMart ELT pipeline indul ===")
    conn = dbm.connect()
    s3 = lakem.make_client()
    lakem.ensure_bucket(s3, config.MINIO["bucket"])
    products = bootstrap(conn, s3)

    log.info("Folyamatos betöltés indul — %d sor / %d mp", config.BATCH_SIZE, config.INTERVAL)
    cycle = 0
    while True:
        cycle += 1
        t0 = time.time()
        try:
            batch = gen.make_order_batch(products, config.N_CUSTOMERS, config.BATCH_SIZE)
            now = datetime.now(timezone.utc)

            # BRONZE — nyers adat a data lake-be, particionált kulccsal
            key = f"raw/orders/dt={now:%Y-%m-%d}/orders_{now:%H%M%S}_{cycle:06d}.json"
            lakem.put_ndjson(s3, config.MINIO["bucket"], key, batch)

            # SILVER — staging
            load_staging(conn, batch)

            # GOLD — dim_date + fact
            ensure_dates(conn, {datetime.fromisoformat(r["order_ts"]).date() for r in batch})
            loaded = load_facts(conn, [r["order_id"] for r in batch])

            duration = int((time.time() - t0) * 1000)
            log_run(conn, len(batch), len(batch), loaded, key, duration, "OK")
            log.info("Ciklus %d | bronze=%s | sorok=%d | fact+=%d | %dms",
                     cycle, key, len(batch), loaded, duration)

        except Exception as exc:  # noqa: BLE001
            log.exception("Ciklus %d hiba: %s", cycle, exc)
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            # Megpróbáljuk újraépíteni a kapcsolatot, ha megszakadt
            try:
                if conn.closed:
                    conn = dbm.connect()
            except Exception:  # noqa: BLE001
                conn = dbm.connect()

        time.sleep(config.INTERVAL)


if __name__ == "__main__":
    main()
