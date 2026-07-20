-- =============================================================================
-- FILE       : 02_reporting_queries.sql
-- PROJECT    : NusantaraTech E-Commerce Data Mart
-- AUTHOR     : Muhammad Zidane Alhalita
-- PURPOSE    : Kumpulan query analitik/reporting (MIS) yang siap dipakai oleh
--              business user, dashboard (reports/generate_report.py), maupun
--              sebagai starting point analisis ad-hoc.
-- NOTES      : Semua query mengasumsikan data mart sudah ter-load penuh
--              (jalankan `python -m etl.run_etl` terlebih dahulu).
-- =============================================================================


-- =============================================================================
-- A. SALES & REVENUE PERFORMANCE (sumber: fact_orders)
-- =============================================================================

-- A1. Ringkasan KPI penjualan bulanan: total order, revenue, profit, AOV
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(*)                                   AS total_order,
    SUM(fo.quantity)                           AS total_unit_terjual,
    SUM(fo.gross_revenue_idr)                  AS total_revenue_idr,
    SUM(fo.gross_profit_idr)                   AS total_profit_idr,
    ROUND(SUM(fo.gross_revenue_idr) * 1.0 / COUNT(*), 0) AS avg_order_value_idr
FROM fact_orders fo
JOIN dim_date d ON fo.date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- A2. Revenue & profit per kategori produk, diurutkan dari terbesar
SELECT
    dp.kategori,
    COUNT(*)                    AS total_order,
    SUM(fo.quantity)            AS total_unit_terjual,
    SUM(fo.gross_revenue_idr)   AS total_revenue_idr,
    SUM(fo.gross_profit_idr)    AS total_profit_idr,
    ROUND(AVG(dp.margin_pct), 2) AS avg_margin_pct
FROM fact_orders fo
JOIN dim_product dp ON fo.product_key = dp.product_key
GROUP BY dp.kategori
ORDER BY total_revenue_idr DESC;


-- A3. Top 10 produk terlaris berdasarkan revenue (khusus status Delivered)
SELECT
    dp.product_id,
    dp.nama_produk,
    dp.kategori,
    SUM(fo.quantity)          AS total_unit_terjual,
    SUM(fo.gross_revenue_idr) AS total_revenue_idr,
    SUM(fo.gross_profit_idr)  AS total_profit_idr
FROM fact_orders fo
JOIN dim_product dp ON fo.product_key = dp.product_key
WHERE fo.is_delivered = 1
GROUP BY dp.product_id, dp.nama_produk, dp.kategori
ORDER BY total_revenue_idr DESC
LIMIT 10;


-- A4. Distribusi status order (funnel fulfilment) & persentasenya
SELECT
    status_order,
    COUNT(*) AS jumlah_order,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fact_orders), 2) AS persentase
FROM fact_orders
GROUP BY status_order
ORDER BY jumlah_order DESC;


-- A5. Preferensi metode pembayaran & rata-rata nilai transaksinya
SELECT
    dpm.payment_method_name,
    dpm.payment_category,
    COUNT(*)                                             AS total_order,
    SUM(fo.gross_revenue_idr)                            AS total_revenue_idr,
    ROUND(AVG(fo.gross_revenue_idr), 0)                  AS avg_order_value_idr
FROM fact_orders fo
JOIN dim_payment_method dpm ON fo.payment_method_key = dpm.payment_method_key
GROUP BY dpm.payment_method_name, dpm.payment_category
ORDER BY total_revenue_idr DESC;


-- A6. Revenue per kota pelanggan (mengukur kekuatan pasar tiap kota)
SELECT
    dc.kota,
    COUNT(DISTINCT dc.customer_key) AS jumlah_pelanggan,
    COUNT(fo.order_key)             AS total_order,
    SUM(fo.gross_revenue_idr)       AS total_revenue_idr,
    ROUND(SUM(fo.gross_revenue_idr) * 1.0 / COUNT(DISTINCT dc.customer_key), 0) AS revenue_per_customer_idr
FROM fact_orders fo
JOIN dim_customer dc ON fo.customer_key = dc.customer_key
GROUP BY dc.kota
ORDER BY total_revenue_idr DESC;


-- =============================================================================
-- B. CUSTOMER ANALYTICS (sumber: dim_customer + fact_orders)
-- =============================================================================

-- B1. Segmentasi revenue berdasarkan account_tier (Platinum/Gold/Silver/Standard)
SELECT
    dc.account_tier,
    COUNT(DISTINCT dc.customer_key) AS jumlah_pelanggan,
    COUNT(fo.order_key)             AS total_order,
    SUM(fo.gross_revenue_idr)       AS total_revenue_idr,
    ROUND(SUM(fo.gross_revenue_idr) * 1.0 / NULLIF(COUNT(fo.order_key), 0), 0) AS avg_order_value_idr
FROM dim_customer dc
LEFT JOIN fact_orders fo ON dc.customer_key = fo.customer_key
GROUP BY dc.account_tier
ORDER BY total_revenue_idr DESC;


-- B2. Top 10 pelanggan dengan total belanja tertinggi (Customer Lifetime Value sederhana)
SELECT
    dc.user_id,
    dc.nama_lengkap,
    dc.kota,
    dc.account_tier,
    COUNT(fo.order_key)       AS total_order,
    SUM(fo.gross_revenue_idr) AS total_belanja_idr
FROM fact_orders fo
JOIN dim_customer dc ON fo.customer_key = dc.customer_key
WHERE fo.is_delivered = 1
GROUP BY dc.user_id, dc.nama_lengkap, dc.kota, dc.account_tier
ORDER BY total_belanja_idr DESC
LIMIT 10;


-- B3. Pelanggan yang sudah signup tapi BELUM PERNAH order sama sekali
--     (kandidat kampanye reaktivasi / onboarding)
SELECT
    dc.user_id,
    dc.nama_lengkap,
    dc.kota,
    dc.account_tier,
    dc.signup_date,
    dc.tenure_days_as_of_load
FROM dim_customer dc
LEFT JOIN fact_orders fo ON dc.customer_key = fo.customer_key
WHERE fo.order_key IS NULL
ORDER BY dc.tenure_days_as_of_load DESC
LIMIT 20;


-- =============================================================================
-- C. WEB ANALYTICS / CONVERSION FUNNEL (sumber: fact_web_clickstream)
-- =============================================================================

-- C1. Funnel konversi: jumlah event & unique session per tahap funnel
SELECT
    dpg.funnel_order,
    dpg.funnel_stage,
    dpg.page_url,
    COUNT(*)                       AS total_hit,
    COUNT(DISTINCT fwc.session_id) AS unique_session
FROM fact_web_clickstream fwc
JOIN dim_page dpg ON fwc.page_key = dpg.page_key
GROUP BY dpg.funnel_order, dpg.funnel_stage, dpg.page_url
ORDER BY dpg.funnel_order;


-- C2. Rata-rata response time (ms) per halaman -> indikator performa teknis situs
SELECT
    dpg.page_url,
    COUNT(*)                          AS total_hit,
    ROUND(AVG(fwc.response_time_ms),1) AS avg_response_time_ms,
    MAX(fwc.response_time_ms)          AS max_response_time_ms
FROM fact_web_clickstream fwc
JOIN dim_page dpg ON fwc.page_key = dpg.page_key
GROUP BY dpg.page_url
ORDER BY avg_response_time_ms DESC;


-- C3. Distribusi trafik berdasarkan device/platform
SELECT
    dd.platform,
    dd.operating_system,
    COUNT(*)                       AS total_hit,
    COUNT(DISTINCT fwc.session_id) AS unique_session
FROM fact_web_clickstream fwc
JOIN dim_device dd ON fwc.device_key = dd.device_key
GROUP BY dd.platform, dd.operating_system
ORDER BY total_hit DESC;


-- C4. Bandingkan customer yang browsing (clickstream) vs yang benar-benar checkout
--     -> browse-to-buy conversion rate per kota
SELECT
    dc.kota,
    COUNT(DISTINCT fwc.customer_key)                                            AS jumlah_visitor,
    COUNT(DISTINCT CASE WHEN fo.order_key IS NOT NULL THEN fwc.customer_key END) AS jumlah_yang_order,
    ROUND(
        COUNT(DISTINCT CASE WHEN fo.order_key IS NOT NULL THEN fwc.customer_key END) * 100.0
        / NULLIF(COUNT(DISTINCT fwc.customer_key), 0), 2
    ) AS conversion_rate_pct
FROM fact_web_clickstream fwc
JOIN dim_customer dc ON fwc.customer_key = dc.customer_key
LEFT JOIN fact_orders fo ON fo.customer_key = fwc.customer_key
GROUP BY dc.kota
ORDER BY conversion_rate_pct DESC;


-- =============================================================================
-- D. INVENTORY / WAREHOUSE ANALYTICS (sumber: fact_inventory_movements)
-- =============================================================================

-- D1. Posisi stok bersih (net stock) saat ini per produk per gudang
SELECT
    dp.product_id,
    dp.nama_produk,
    dw.warehouse_name,
    SUM(fim.signed_quantity) AS estimasi_stok_bersih
FROM fact_inventory_movements fim
JOIN dim_product dp   ON fim.product_key = dp.product_key
JOIN dim_warehouse dw ON fim.warehouse_key = dw.warehouse_key
GROUP BY dp.product_id, dp.nama_produk, dw.warehouse_name
ORDER BY estimasi_stok_bersih ASC
LIMIT 20;   -- 20 kombinasi produk-gudang dengan stok TERENDAH (butuh restock)


-- D2. Ringkasan pergerakan stok per gudang per jenis mutasi
SELECT
    dw.warehouse_name,
    fim.jenis_mutasi,
    COUNT(*)                       AS jumlah_transaksi,
    SUM(fim.quantity_change)       AS total_unit_bergerak,
    SUM(fim.signed_quantity)       AS net_effect_terhadap_stok
FROM fact_inventory_movements fim
JOIN dim_warehouse dw ON fim.warehouse_key = dw.warehouse_key
GROUP BY dw.warehouse_name, fim.jenis_mutasi
ORDER BY dw.warehouse_name,
    CASE fim.jenis_mutasi
        WHEN 'INBOUND' THEN 1 WHEN 'RETUR_STOCK' THEN 2
        WHEN 'OUTBOUND' THEN 3 WHEN 'ADJUSTMENT_DEFECT' THEN 4 END;


-- D3. Produk dengan tingkat kerusakan (ADJUSTMENT_DEFECT) tertinggi -> quality control
SELECT
    dp.product_id,
    dp.nama_produk,
    dp.kategori,
    SUM(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN fim.quantity_change ELSE 0 END) AS total_unit_rusak,
    COUNT(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN 1 END)                         AS jumlah_kejadian
FROM fact_inventory_movements fim
JOIN dim_product dp ON fim.product_key = dp.product_key
GROUP BY dp.product_id, dp.nama_produk, dp.kategori
HAVING total_unit_rusak > 0
ORDER BY total_unit_rusak DESC
LIMIT 10;


-- =============================================================================
-- E. CROSS-DOMAIN / EXECUTIVE SUMMARY
--    Query yang menggabungkan >=2 fact table sekaligus - contoh nyata manfaat
--    data mart terpusat dibanding harus query berpindah-pindah ke 5 sistem asal.
-- =============================================================================

-- E1. Executive summary harian: revenue penjualan vs aktivitas web vs pergerakan gudang
SELECT
    d.full_date,
    COALESCE(sales.total_order, 0)        AS total_order,
    COALESCE(sales.total_revenue_idr, 0)  AS total_revenue_idr,
    COALESCE(web.total_hit, 0)            AS total_web_hit,
    COALESCE(web.unique_session, 0)       AS unique_session,
    COALESCE(inv.total_movement, 0)       AS total_pergerakan_gudang
FROM dim_date d
LEFT JOIN (
    SELECT date_key, COUNT(*) AS total_order, SUM(gross_revenue_idr) AS total_revenue_idr
    FROM fact_orders GROUP BY date_key
) sales ON d.date_key = sales.date_key
LEFT JOIN (
    SELECT date_key, COUNT(*) AS total_hit, COUNT(DISTINCT session_id) AS unique_session
    FROM fact_web_clickstream GROUP BY date_key
) web ON d.date_key = web.date_key
LEFT JOIN (
    SELECT date_key, COUNT(*) AS total_movement
    FROM fact_inventory_movements GROUP BY date_key
) inv ON d.date_key = inv.date_key
WHERE d.full_date BETWEEN '2026-06-01' AND '2026-06-30'
ORDER BY d.full_date;


-- E2. Kategori produk paling menguntungkan (revenue TINGGI) namun paling sering RUSAK
--     di gudang -> kandidat evaluasi supplier / kualitas produk
SELECT
    dp.kategori,
    SUM(fo.gross_revenue_idr) AS total_revenue_idr,
    SUM(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN fim.quantity_change ELSE 0 END) AS total_unit_rusak
FROM dim_product dp
LEFT JOIN fact_orders fo ON dp.product_key = fo.product_key
LEFT JOIN fact_inventory_movements fim ON dp.product_key = fim.product_key
GROUP BY dp.kategori
ORDER BY total_revenue_idr DESC;
