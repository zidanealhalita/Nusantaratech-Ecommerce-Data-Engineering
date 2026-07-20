-- =============================================================================
-- FILE       : 01_create_schema.sql
-- PROJECT    : NusantaraTech E-Commerce Data Mart
-- AUTHOR     : Muhammad Zidane Alhalita
-- PURPOSE    : Membuat seluruh struktur tabel data mart (staging, dimensi, fakta)
--              menggunakan pendekatan Kimball Star Schema.
-- ENGINE     : SQLite 3 (portable, cocok untuk demo/portfolio project)
-- NOTES      : Jalankan script ini sebelum proses ETL (etl/run_etl.py).
--              Script bersifat idempotent (DROP TABLE IF EXISTS sebelum CREATE).
-- =============================================================================

PRAGMA foreign_keys = ON;

-- =============================================================================
-- 1. STAGING LAYER
--    Tabel staging menampung data mentah (raw) hasil EXTRACT dari 5 source
--    system sebelum dibersihkan/ditransformasi. Struktur staging sengaja dibuat
--    mirip 1:1 dengan file sumber (schema-on-read) agar mudah divalidasi/diaudit.
-- =============================================================================

DROP TABLE IF EXISTS stg_crm_user_profiles;
CREATE TABLE stg_crm_user_profiles (
    user_id             TEXT,
    nama_lengkap        TEXT,
    email               TEXT,
    kota                TEXT,
    account_tier        TEXT,
    signup_timestamp    TEXT,
    _loaded_at          TEXT DEFAULT (datetime('now'))
);

DROP TABLE IF EXISTS stg_mdm_products;
CREATE TABLE stg_mdm_products (
    product_id          TEXT,
    nama_produk         TEXT,
    kategori            TEXT,
    harga_modal_idr     INTEGER,
    harga_jual_idr      INTEGER,
    is_active           TEXT,
    _loaded_at          TEXT DEFAULT (datetime('now'))
);

DROP TABLE IF EXISTS stg_oms_orders;
CREATE TABLE stg_oms_orders (
    order_id            TEXT,
    user_id             TEXT,
    product_id          TEXT,
    jumlah_barang       INTEGER,
    order_timestamp     TEXT,
    metode_pembayaran   TEXT,
    status_order        TEXT,
    _loaded_at          TEXT DEFAULT (datetime('now'))
);

DROP TABLE IF EXISTS stg_web_clickstream_logs;
CREATE TABLE stg_web_clickstream_logs (
    log_id              TEXT,
    session_id          TEXT,
    user_id             TEXT,
    hit_timestamp       TEXT,
    page_url            TEXT,
    ip_address          TEXT,
    device_type         TEXT,
    response_time_ms    INTEGER,
    _loaded_at          TEXT DEFAULT (datetime('now'))
);

DROP TABLE IF EXISTS stg_wms_inventory_movements;
CREATE TABLE stg_wms_inventory_movements (
    movement_id             TEXT,
    product_id               TEXT,
    warehouse_id             TEXT,
    jenis_mutasi             TEXT,
    kuantitas_perubahan      INTEGER,
    recorded_timestamp       TEXT,
    operator_id              TEXT,
    _loaded_at                TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- 2. DIMENSION LAYER
--    Conformed dimensions yang dipakai bersama oleh lebih dari satu fact table.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- dim_date : dimensi waktu standar, digenerate oleh ETL (bukan dari source),
--            dipakai oleh ketiga fact table sebagai conformed dimension.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,   -- format YYYYMMDD
    full_date       TEXT NOT NULL,         -- YYYY-MM-DD
    day             INTEGER NOT NULL,
    day_name        TEXT NOT NULL,
    month           INTEGER NOT NULL,
    month_name      TEXT NOT NULL,
    quarter         INTEGER NOT NULL,
    year            INTEGER NOT NULL,
    week_of_year    INTEGER NOT NULL,
    is_weekend      INTEGER NOT NULL       -- 1 = Sabtu/Minggu, 0 = weekday
);

-- ---------------------------------------------------------------------------
-- dim_customer : SCD Type 1, sumber = CRM
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer (
    customer_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              TEXT NOT NULL UNIQUE,      -- natural key
    nama_lengkap         TEXT NOT NULL,
    email                TEXT NOT NULL,
    kota                 TEXT NOT NULL,
    account_tier         TEXT NOT NULL,
    signup_date          TEXT NOT NULL,
    signup_datetime      TEXT NOT NULL,
    tenure_days_as_of_load INTEGER,               -- lama gabung (hari) dihitung saat ETL
    _loaded_at            TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_dim_customer_kota ON dim_customer(kota);
CREATE INDEX idx_dim_customer_tier ON dim_customer(account_tier);

-- ---------------------------------------------------------------------------
-- dim_product : SCD Type 1, sumber = MDM
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product (
    product_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id         TEXT NOT NULL UNIQUE,       -- natural key
    nama_produk        TEXT NOT NULL,
    kategori           TEXT NOT NULL,
    harga_modal_idr    INTEGER NOT NULL,
    harga_jual_idr     INTEGER NOT NULL,
    margin_idr         INTEGER NOT NULL,           -- harga_jual - harga_modal
    margin_pct         REAL NOT NULL,               -- margin_idr / harga_jual * 100
    is_active          INTEGER NOT NULL,            -- 1/0
    _loaded_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_dim_product_kategori ON dim_product(kategori);

-- ---------------------------------------------------------------------------
-- dim_warehouse : diturunkan (derived) dari warehouse_id pada WMS
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_warehouse;
CREATE TABLE dim_warehouse (
    warehouse_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id      TEXT NOT NULL UNIQUE,        -- natural key, contoh: WH-JAKARTA-01
    warehouse_name    TEXT NOT NULL,                -- contoh: "Jakarta"
    warehouse_code    TEXT NOT NULL                 -- contoh: "01"
);

-- ---------------------------------------------------------------------------
-- dim_payment_method : mini-dimension dari OMS.metode_pembayaran
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_payment_method;
CREATE TABLE dim_payment_method (
    payment_method_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_method_code    TEXT NOT NULL UNIQUE,   -- contoh: VA_BCA
    payment_method_name    TEXT NOT NULL,           -- contoh: "Virtual Account BCA"
    payment_category       TEXT NOT NULL            -- E-Wallet / Virtual Account / Kartu Kredit
);

-- ---------------------------------------------------------------------------
-- dim_device : mini-dimension dari WEB.device_type
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_device;
CREATE TABLE dim_device (
    device_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    device_type_code  TEXT NOT NULL UNIQUE,        -- contoh: Mobile-Android
    platform          TEXT NOT NULL,                -- Desktop / Mobile
    operating_system  TEXT NOT NULL                 -- MacOS / Windows / Android / iOS
);

-- ---------------------------------------------------------------------------
-- dim_page : mini-dimension dari WEB.page_url, dipetakan ke tahap funnel
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_page;
CREATE TABLE dim_page (
    page_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url        TEXT NOT NULL UNIQUE,
    funnel_stage    TEXT NOT NULL,                  -- Landing/Discovery/Consideration/Intent/Conversion/Purchase
    funnel_order    INTEGER NOT NULL                -- urutan tahap funnel (1..6) untuk sorting
);

-- =============================================================================
-- 3. FACT LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- fact_orders : grain = 1 baris per order (1 order = 1 baris produk, sesuai OMS)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_orders;
CREATE TABLE fact_orders (
    order_key          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            TEXT NOT NULL UNIQUE,        -- degenerate dimension
    date_key             INTEGER NOT NULL,
    order_datetime        TEXT NOT NULL,
    customer_key          INTEGER NOT NULL,
    product_key            INTEGER NOT NULL,
    payment_method_key     INTEGER NOT NULL,
    status_order            TEXT NOT NULL,            -- degenerate dimension
    quantity                 INTEGER NOT NULL,
    unit_price_idr             INTEGER NOT NULL,
    unit_cost_idr               INTEGER NOT NULL,
    gross_revenue_idr             INTEGER NOT NULL,   -- quantity * unit_price_idr
    gross_cost_idr                 INTEGER NOT NULL,  -- quantity * unit_cost_idr
    gross_profit_idr                INTEGER NOT NULL, -- revenue - cost
    is_delivered                      INTEGER NOT NULL, -- flag 1/0
    is_cancelled                       INTEGER NOT NULL,
    is_returned                         INTEGER NOT NULL,
    FOREIGN KEY (date_key)          REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_key)      REFERENCES dim_customer(customer_key),
    FOREIGN KEY (product_key)       REFERENCES dim_product(product_key),
    FOREIGN KEY (payment_method_key) REFERENCES dim_payment_method(payment_method_key)
);
CREATE INDEX idx_fact_orders_date ON fact_orders(date_key);
CREATE INDEX idx_fact_orders_customer ON fact_orders(customer_key);
CREATE INDEX idx_fact_orders_product ON fact_orders(product_key);
CREATE INDEX idx_fact_orders_status ON fact_orders(status_order);

-- ---------------------------------------------------------------------------
-- fact_inventory_movements : grain = 1 baris per pergerakan stok gudang
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_inventory_movements;
CREATE TABLE fact_inventory_movements (
    movement_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    movement_id           TEXT NOT NULL UNIQUE,
    date_key                INTEGER NOT NULL,
    movement_datetime         TEXT NOT NULL,
    product_key                 INTEGER NOT NULL,
    warehouse_key                 INTEGER NOT NULL,
    jenis_mutasi                    TEXT NOT NULL,     -- degenerate dimension
    operator_id                       TEXT NOT NULL,    -- degenerate dimension
    quantity_change                     INTEGER NOT NULL, -- nilai absolut asli dari source
    signed_quantity                       INTEGER NOT NULL, -- (+) menambah stok, (-) mengurangi stok
    FOREIGN KEY (date_key)      REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key)   REFERENCES dim_product(product_key),
    FOREIGN KEY (warehouse_key) REFERENCES dim_warehouse(warehouse_key)
);
CREATE INDEX idx_fact_inv_date ON fact_inventory_movements(date_key);
CREATE INDEX idx_fact_inv_product ON fact_inventory_movements(product_key);
CREATE INDEX idx_fact_inv_warehouse ON fact_inventory_movements(warehouse_key);
CREATE INDEX idx_fact_inv_jenis ON fact_inventory_movements(jenis_mutasi);

-- ---------------------------------------------------------------------------
-- fact_web_clickstream : grain = 1 baris per page-hit / event klik
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_web_clickstream;
CREATE TABLE fact_web_clickstream (
    click_key         INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id              TEXT NOT NULL UNIQUE,
    date_key               INTEGER NOT NULL,
    hit_datetime              TEXT NOT NULL,
    session_id                  TEXT NOT NULL,
    customer_key                  INTEGER,             -- nullable: bisa saja anonim di masa depan
    page_key                        INTEGER NOT NULL,
    device_key                        INTEGER NOT NULL,
    ip_address                          TEXT NOT NULL,
    response_time_ms                      INTEGER NOT NULL,
    FOREIGN KEY (date_key)     REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY (page_key)     REFERENCES dim_page(page_key),
    FOREIGN KEY (device_key)   REFERENCES dim_device(device_key)
);
CREATE INDEX idx_fact_click_date ON fact_web_clickstream(date_key);
CREATE INDEX idx_fact_click_customer ON fact_web_clickstream(customer_key);
CREATE INDEX idx_fact_click_session ON fact_web_clickstream(session_id);
CREATE INDEX idx_fact_click_page ON fact_web_clickstream(page_key);

-- =============================================================================
-- 4. ETL AUDIT LOG
--    Tabel metadata untuk mencatat histori setiap kali pipeline ETL dijalankan
--    (praktik umum di Data Warehouse untuk observability & troubleshooting).
-- =============================================================================
DROP TABLE IF EXISTS etl_run_log;
CREATE TABLE etl_run_log (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    step_name         TEXT NOT NULL,
    status              TEXT NOT NULL,      -- SUCCESS / FAILED
    row_count             INTEGER,
    started_at              TEXT NOT NULL,
    finished_at               TEXT NOT NULL,
    notes                       TEXT
);
