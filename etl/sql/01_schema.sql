-- =============================================================================
--  01_schema.sql  —  Adattárház séma (idempotens, IF NOT EXISTS)
--  Rétegek:  stg_*  = SILVER (tisztított, konformált)
--            dim_* / fact_* = GOLD (dimenzionális star schema)
-- =============================================================================

-- ---------------------------------------------------------------------------
--  SILVER — staging réteg (a bronze-ból betöltött, validált rendelések)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_orders (
    order_id      BIGINT       PRIMARY KEY,
    order_ts      TIMESTAMPTZ  NOT NULL,
    customer_id   INTEGER      NOT NULL,
    product_id    INTEGER      NOT NULL,
    quantity      INTEGER      NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL,
    discount_pct  NUMERIC(5,2)  NOT NULL DEFAULT 0,
    channel       TEXT         NOT NULL,
    loaded_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
--  GOLD — dimenziók
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id  INTEGER PRIMARY KEY,
    full_name    TEXT    NOT NULL,
    email        TEXT,
    country      TEXT    NOT NULL,
    city         TEXT,
    segment      TEXT    NOT NULL,
    signup_date  DATE
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    brand         TEXT    NOT NULL,
    unit_cost     NUMERIC(10,2) NOT NULL,
    list_price    NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,   -- formátum: YYYYMMDD
    date          DATE    NOT NULL,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT    NOT NULL,
    day           INTEGER NOT NULL,
    weekday       INTEGER NOT NULL,      -- ISO: 1=hétfő ... 7=vasárnap
    weekday_name  TEXT    NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

-- ---------------------------------------------------------------------------
--  GOLD — ténytábla (star schema központja)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_sales (
    order_id        BIGINT       PRIMARY KEY,
    order_ts        TIMESTAMPTZ  NOT NULL,
    date_key        INTEGER      NOT NULL REFERENCES dim_date(date_key),
    customer_id     INTEGER      NOT NULL REFERENCES dim_customer(customer_id),
    product_id      INTEGER      NOT NULL REFERENCES dim_product(product_id),
    channel         TEXT         NOT NULL,
    quantity        INTEGER      NOT NULL,
    unit_price      NUMERIC(10,2) NOT NULL,
    discount_pct    NUMERIC(5,2)  NOT NULL,
    gross_amount    NUMERIC(12,2) NOT NULL,   -- bruttó (kedvezmény előtt)
    discount_amount NUMERIC(12,2) NOT NULL,
    net_amount      NUMERIC(12,2) NOT NULL,   -- nettó árbevétel
    margin_amount   NUMERIC(12,2) NOT NULL    -- fedezet (nettó - bekerülési)
);

CREATE INDEX IF NOT EXISTS idx_fact_ts       ON fact_sales (order_ts);
CREATE INDEX IF NOT EXISTS idx_fact_datekey  ON fact_sales (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_product  ON fact_sales (product_id);
CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales (customer_id);

-- ---------------------------------------------------------------------------
--  OBSERVABILITY — ETL futási napló (a pipeline saját telemetriája)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id        BIGSERIAL   PRIMARY KEY,
    run_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    batch_size    INTEGER,
    rows_bronze   INTEGER,
    rows_loaded   INTEGER,
    bronze_object TEXT,
    duration_ms   INTEGER,
    status        TEXT
);
