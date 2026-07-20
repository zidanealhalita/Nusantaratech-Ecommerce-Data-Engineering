-- =============================================================================
-- FILE       : 03_data_quality_checks.sql
-- PROJECT    : NusantaraTech E-Commerce Data Mart
-- AUTHOR     : Muhammad Zidane Alhalita
-- PURPOSE    : Versi murni SQL dari data quality check (setara dengan
--              etl/data_quality.py), agar bisa langsung dijalankan lewat
--              SQL client (DBeaver/DB Browser for SQLite) tanpa Python.
--              Setiap query idealnya mengembalikan 0 baris jika data VALID.
-- =============================================================================

-- DQ-1. Row count reconciliation: staging vs dimension/fact (harus identik)
SELECT 'crm_vs_dim_customer' AS check_name,
       (SELECT COUNT(*) FROM stg_crm_user_profiles) AS staging_count,
       (SELECT COUNT(*) FROM dim_customer) AS mart_count
UNION ALL
SELECT 'mdm_vs_dim_product',
       (SELECT COUNT(*) FROM stg_mdm_products),
       (SELECT COUNT(*) FROM dim_product)
UNION ALL
SELECT 'oms_vs_fact_orders',
       (SELECT COUNT(*) FROM stg_oms_orders),
       (SELECT COUNT(*) FROM fact_orders)
UNION ALL
SELECT 'wms_vs_fact_inventory',
       (SELECT COUNT(*) FROM stg_wms_inventory_movements),
       (SELECT COUNT(*) FROM fact_inventory_movements)
UNION ALL
SELECT 'web_vs_fact_clickstream',
       (SELECT COUNT(*) FROM stg_web_clickstream_logs),
       (SELECT COUNT(*) FROM fact_web_clickstream);


-- DQ-2. Orphan foreign key check pada fact_orders (harus 0 baris)
SELECT order_id, customer_key, product_key, payment_method_key
FROM fact_orders
WHERE customer_key IS NULL OR product_key IS NULL OR payment_method_key IS NULL;


-- DQ-3. Orphan foreign key check pada fact_inventory_movements (harus 0 baris)
SELECT movement_id, product_key, warehouse_key
FROM fact_inventory_movements
WHERE product_key IS NULL OR warehouse_key IS NULL;


-- DQ-4. Orphan foreign key check pada fact_web_clickstream (harus 0 baris)
SELECT log_id, page_key, device_key
FROM fact_web_clickstream
WHERE page_key IS NULL OR device_key IS NULL;


-- DQ-5. Duplikasi natural key di tabel dimensi (harus 0 baris)
SELECT 'dim_customer.user_id' AS kolom, user_id AS nilai, COUNT(*) AS jumlah
FROM dim_customer GROUP BY user_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'dim_product.product_id', product_id, COUNT(*)
FROM dim_product GROUP BY product_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'fact_orders.order_id', order_id, COUNT(*)
FROM fact_orders GROUP BY order_id HAVING COUNT(*) > 1;


-- DQ-6. Business rule: revenue & quantity harus positif (harus 0 baris)
SELECT order_id, quantity, gross_revenue_idr
FROM fact_orders
WHERE quantity <= 0 OR gross_revenue_idr < 0;


-- DQ-7. Business rule: margin_pct produk harus berada di rentang wajar 0-100% (harus 0 baris)
SELECT product_id, margin_idr, margin_pct
FROM dim_product
WHERE margin_pct < 0 OR margin_pct > 100;


-- DQ-8. Business rule: setiap fact_orders.date_key harus ada di dim_date (harus 0 baris)
SELECT fo.order_id, fo.date_key
FROM fact_orders fo
LEFT JOIN dim_date d ON fo.date_key = d.date_key
WHERE d.date_key IS NULL;


-- DQ-9. Ringkasan histori eksekusi ETL (audit trail)
SELECT step_name, status, row_count, started_at, finished_at
FROM etl_run_log
ORDER BY run_id DESC
LIMIT 20;
