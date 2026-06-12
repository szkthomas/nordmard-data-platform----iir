-- =============================================================================
--  02_marts.sql  —  Analitikai "data mart" nézetek (Grafana fogyasztja)
--  Üzleti kérdésekre adott, lekérdezésre kész aggregátumok.
-- =============================================================================

-- Fő KPI-k (egysoros összegzés)
CREATE OR REPLACE VIEW mart_kpis AS
SELECT
    count(*)                                  AS total_orders,
    COALESCE(sum(net_amount), 0)              AS total_revenue,
    COALESCE(round(avg(net_amount), 2), 0)    AS avg_order_value,
    count(DISTINCT customer_id)               AS active_customers,
    COALESCE(sum(margin_amount), 0)           AS total_margin
FROM fact_sales;

-- Árbevétel idősor (percre aggregálva) — Grafana time series panelhez
CREATE OR REPLACE VIEW mart_revenue_timeseries AS
SELECT
    date_trunc('minute', order_ts) AS time,
    sum(net_amount)                AS revenue,
    sum(margin_amount)             AS margin,
    sum(quantity)                  AS units,
    count(*)                       AS orders
FROM fact_sales
GROUP BY 1
ORDER BY 1;

-- Árbevétel kategóriánként
CREATE OR REPLACE VIEW mart_revenue_by_category AS
SELECT
    p.category,
    sum(f.net_amount)   AS revenue,
    sum(f.margin_amount) AS margin,
    sum(f.quantity)     AS units
FROM fact_sales f
JOIN dim_product p USING (product_id)
GROUP BY p.category
ORDER BY revenue DESC;

-- Top 10 termék árbevétel szerint
CREATE OR REPLACE VIEW mart_top_products AS
SELECT
    p.product_name,
    p.category,
    sum(f.net_amount) AS revenue,
    sum(f.quantity)   AS units
FROM fact_sales f
JOIN dim_product p USING (product_id)
GROUP BY p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;

-- Árbevétel ország szerint
CREATE OR REPLACE VIEW mart_revenue_by_country AS
SELECT
    c.country,
    sum(f.net_amount)            AS revenue,
    count(DISTINCT f.customer_id) AS customers
FROM fact_sales f
JOIN dim_customer c USING (customer_id)
GROUP BY c.country
ORDER BY revenue DESC;

-- Árbevétel értékesítési csatornánként
CREATE OR REPLACE VIEW mart_channel_share AS
SELECT
    channel,
    sum(net_amount) AS revenue,
    count(*)        AS orders
FROM fact_sales
GROUP BY channel
ORDER BY revenue DESC;
