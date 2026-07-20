# Data Dictionary — NusantaraTech E-Commerce Data Mart

Dokumen ini berisi definisi lengkap setiap kolom pada setiap tabel di data mart
(`db/datamart.db`), mencakup layer **Staging**, **Dimension**, dan **Fact**.

Legenda tipe data mengikuti tipe SQLite (`TEXT`, `INTEGER`, `REAL`).

---

## 1. Staging Layer

Tabel staging adalah salinan mentah (1:1) dari file CSV sumber, digunakan sebagai
titik audit sebelum data dibersihkan/ditransformasi. Prefix: `stg_`.

### 1.1 `stg_crm_user_profiles` (sumber: CRM)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| user_id | TEXT | ID unik pelanggan, format `USR-####` |
| nama_lengkap | TEXT | Nama lengkap pelanggan |
| email | TEXT | Alamat email pelanggan |
| kota | TEXT | Kota domisili pelanggan |
| account_tier | TEXT | Tingkatan akun: Standard / Silver / Gold / Platinum |
| signup_timestamp | TEXT | Waktu pendaftaran akun (`YYYY-MM-DD HH:MM:SS`) |
| _loaded_at | TEXT | Timestamp ETL saat baris ini dimuat ke staging |

### 1.2 `stg_mdm_products` (sumber: MDM)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| product_id | TEXT | ID unik produk, format `PROD-####` |
| nama_produk | TEXT | Nama produk |
| kategori | TEXT | Kategori produk (Beauty & Health, Electronics, dst.) |
| harga_modal_idr | INTEGER | Harga modal/pokok produk (Rupiah) |
| harga_jual_idr | INTEGER | Harga jual produk ke pelanggan (Rupiah) |
| is_active | TEXT | Status aktif produk (`True`/`False` sebagai string dari CSV) |
| _loaded_at | TEXT | Timestamp ETL |

### 1.3 `stg_oms_orders` (sumber: OMS)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| order_id | TEXT | ID unik order, format `ORD-######` |
| user_id | TEXT | FK ke pelanggan yang memesan |
| product_id | TEXT | FK ke produk yang dipesan |
| jumlah_barang | INTEGER | Kuantitas barang dalam order |
| order_timestamp | TEXT | Waktu order dibuat |
| metode_pembayaran | TEXT | Kode metode pembayaran (OVO, DANA, GOPAY, CREDIT_CARD, VA_BCA, VA_MANDIRI) |
| status_order | TEXT | Status order (Pending/Processing/Shipped/Delivered/Cancelled/Returned) |
| _loaded_at | TEXT | Timestamp ETL |

### 1.4 `stg_web_clickstream_logs` (sumber: Web Analytics)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| log_id | TEXT | ID unik event/log, format `LOG-#######` |
| session_id | TEXT | ID sesi browsing pengguna |
| user_id | TEXT | FK ke pelanggan (bisa jadi anonim di masa depan) |
| hit_timestamp | TEXT | Waktu event terjadi |
| page_url | TEXT | Halaman yang diakses (/home, /search, /product/view, dst.) |
| ip_address | TEXT | Alamat IP pengunjung |
| device_type | TEXT | Tipe perangkat & OS (mis. Mobile-Android) |
| response_time_ms | INTEGER | Waktu respon halaman dalam milidetik |
| _loaded_at | TEXT | Timestamp ETL |

### 1.5 `stg_wms_inventory_movements` (sumber: WMS)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| movement_id | TEXT | ID unik pergerakan stok, format `MOV-######` |
| product_id | TEXT | FK ke produk yang bergerak |
| warehouse_id | TEXT | ID gudang, format `WH-<KOTA>-##` |
| jenis_mutasi | TEXT | INBOUND / OUTBOUND / RETUR_STOCK / ADJUSTMENT_DEFECT |
| kuantitas_perubahan | INTEGER | Jumlah unit yang bergerak (nilai absolut) |
| recorded_timestamp | TEXT | Waktu pergerakan dicatat |
| operator_id | TEXT | ID petugas gudang yang mencatat transaksi |
| _loaded_at | TEXT | Timestamp ETL |

---

## 2. Dimension Layer

### 2.1 `dim_date` — Conformed calendar dimension (di-generate oleh ETL)
| Kolom | Tipe | Deskripsi |
|---|---|---|
| date_key | INTEGER (PK) | Format `YYYYMMDD`, mis. `20260615` |
| full_date | TEXT | Tanggal lengkap `YYYY-MM-DD` |
| day | INTEGER | Tanggal (1-31) |
| day_name | TEXT | Nama hari dalam Bahasa Indonesia |
| month | INTEGER | Bulan (1-12) |
| month_name | TEXT | Nama bulan dalam Bahasa Indonesia |
| quarter | INTEGER | Kuartal (1-4) |
| year | INTEGER | Tahun |
| week_of_year | INTEGER | Minggu ke-N dalam tahun (ISO week) |
| is_weekend | INTEGER | 1 jika Sabtu/Minggu, 0 jika hari kerja |

### 2.2 `dim_customer` — SCD Type 1, sumber: CRM
| Kolom | Tipe | Deskripsi |
|---|---|---|
| customer_key | INTEGER (PK) | Surrogate key |
| user_id | TEXT (UNIQUE) | Natural key dari CRM |
| nama_lengkap | TEXT | Nama pelanggan |
| email | TEXT | Email pelanggan |
| kota | TEXT | Kota domisili |
| account_tier | TEXT | Standard/Silver/Gold/Platinum |
| signup_date | TEXT | Tanggal pendaftaran (`YYYY-MM-DD`) |
| signup_datetime | TEXT | Timestamp pendaftaran lengkap |
| tenure_days_as_of_load | INTEGER | Lama keanggotaan (hari) dihitung relatif terhadap tanggal snapshot ETL (2026-07-01) |
| _loaded_at | TEXT | Timestamp ETL |

### 2.3 `dim_product` — SCD Type 1, sumber: MDM
| Kolom | Tipe | Deskripsi |
|---|---|---|
| product_key | INTEGER (PK) | Surrogate key |
| product_id | TEXT (UNIQUE) | Natural key dari MDM |
| nama_produk | TEXT | Nama produk |
| kategori | TEXT | Kategori produk |
| harga_modal_idr | INTEGER | Harga modal (Rupiah) |
| harga_jual_idr | INTEGER | Harga jual (Rupiah) |
| margin_idr | INTEGER | **Turunan**: `harga_jual_idr - harga_modal_idr` |
| margin_pct | REAL | **Turunan**: `margin_idr / harga_jual_idr * 100`, dibulatkan 2 desimal |
| is_active | INTEGER | 1 = aktif dijual, 0 = tidak aktif |
| _loaded_at | TEXT | Timestamp ETL |

### 2.4 `dim_warehouse` — Derived dimension, sumber: WMS
| Kolom | Tipe | Deskripsi |
|---|---|---|
| warehouse_key | INTEGER (PK) | Surrogate key |
| warehouse_id | TEXT (UNIQUE) | Natural key, mis. `WH-JAKARTA-01` |
| warehouse_name | TEXT | **Turunan**: nama kota hasil parsing (mis. `Jakarta`) |
| warehouse_code | TEXT | **Turunan**: kode gudang (mis. `01`) |

### 2.5 `dim_payment_method` — Mini-dimension, sumber: OMS + lookup bisnis
| Kolom | Tipe | Deskripsi |
|---|---|---|
| payment_method_key | INTEGER (PK) | Surrogate key |
| payment_method_code | TEXT (UNIQUE) | Kode asli dari OMS (mis. `VA_BCA`) |
| payment_method_name | TEXT | Nama tampilan yang lebih ramah bisnis (mis. "Virtual Account - BCA") |
| payment_category | TEXT | Kategori: E-Wallet / Virtual Account / Kartu Kredit |

### 2.6 `dim_device` — Derived dimension, sumber: Web Analytics
| Kolom | Tipe | Deskripsi |
|---|---|---|
| device_key | INTEGER (PK) | Surrogate key |
| device_type_code | TEXT (UNIQUE) | Kode asli (mis. `Mobile-Android`) |
| platform | TEXT | **Turunan**: Desktop / Mobile |
| operating_system | TEXT | **Turunan**: MacOS / Windows / Android / iOS |

### 2.7 `dim_page` — Mini-dimension, sumber: Web Analytics + lookup bisnis
| Kolom | Tipe | Deskripsi |
|---|---|---|
| page_key | INTEGER (PK) | Surrogate key |
| page_url | TEXT (UNIQUE) | URL halaman (mis. `/checkout`) |
| funnel_stage | TEXT | Tahap funnel e-commerce (Landing/Discovery/Consideration/Intent/Conversion/Purchase) |
| funnel_order | INTEGER | Urutan numerik tahap funnel (1-6), untuk sorting |

---

## 3. Fact Layer

### 3.1 `fact_orders` — Grain: 1 baris = 1 order
| Kolom | Tipe | Deskripsi |
|---|---|---|
| order_key | INTEGER (PK) | Surrogate key |
| order_id | TEXT (UNIQUE) | Degenerate dimension, natural key dari OMS |
| date_key | INTEGER (FK → dim_date) | Tanggal order |
| order_datetime | TEXT | Timestamp order lengkap |
| customer_key | INTEGER (FK → dim_customer) | Pelanggan yang memesan |
| product_key | INTEGER (FK → dim_product) | Produk yang dipesan |
| payment_method_key | INTEGER (FK → dim_payment_method) | Metode pembayaran |
| status_order | TEXT | Degenerate dimension: status fulfilment order |
| quantity | INTEGER | Measure: jumlah unit dipesan |
| unit_price_idr | INTEGER | Measure: harga jual per unit saat order (snapshot dari dim_product) |
| unit_cost_idr | INTEGER | Measure: harga modal per unit saat order |
| gross_revenue_idr | INTEGER | **Turunan**: `quantity * unit_price_idr` |
| gross_cost_idr | INTEGER | **Turunan**: `quantity * unit_cost_idr` |
| gross_profit_idr | INTEGER | **Turunan**: `gross_revenue_idr - gross_cost_idr` |
| is_delivered | INTEGER | Flag 1/0: `status_order = 'Delivered'` |
| is_cancelled | INTEGER | Flag 1/0: `status_order = 'Cancelled'` |
| is_returned | INTEGER | Flag 1/0: `status_order = 'Returned'` |

### 3.2 `fact_inventory_movements` — Grain: 1 baris = 1 pergerakan stok
| Kolom | Tipe | Deskripsi |
|---|---|---|
| movement_key | INTEGER (PK) | Surrogate key |
| movement_id | TEXT (UNIQUE) | Natural key dari WMS |
| date_key | INTEGER (FK → dim_date) | Tanggal pergerakan |
| movement_datetime | TEXT | Timestamp pergerakan lengkap |
| product_key | INTEGER (FK → dim_product) | Produk yang bergerak |
| warehouse_key | INTEGER (FK → dim_warehouse) | Gudang lokasi pergerakan |
| jenis_mutasi | TEXT | Degenerate dimension: INBOUND/OUTBOUND/RETUR_STOCK/ADJUSTMENT_DEFECT |
| operator_id | TEXT | Degenerate dimension: petugas yang mencatat |
| quantity_change | INTEGER | Measure: jumlah unit (nilai absolut asli dari source) |
| signed_quantity | INTEGER | **Turunan**: quantity_change bertanda (+) untuk INBOUND/RETUR_STOCK, (-) untuk OUTBOUND/ADJUSTMENT_DEFECT — memungkinkan `SUM()` langsung merepresentasikan perubahan stok bersih |

### 3.3 `fact_web_clickstream` — Grain: 1 baris = 1 page-hit
| Kolom | Tipe | Deskripsi |
|---|---|---|
| click_key | INTEGER (PK) | Surrogate key |
| log_id | TEXT (UNIQUE) | Natural key dari Web Analytics |
| date_key | INTEGER (FK → dim_date) | Tanggal event |
| hit_datetime | TEXT | Timestamp event lengkap |
| session_id | TEXT | ID sesi browsing |
| customer_key | INTEGER (FK → dim_customer, nullable) | Pelanggan (nullable untuk mengantisipasi trafik anonim) |
| page_key | INTEGER (FK → dim_page) | Halaman yang diakses |
| device_key | INTEGER (FK → dim_device) | Perangkat yang digunakan |
| ip_address | TEXT | Alamat IP pengunjung |
| response_time_ms | INTEGER | Measure: waktu respon halaman (ms) |

---

## 4. Tabel Metadata

### 4.1 `etl_run_log`
| Kolom | Tipe | Deskripsi |
|---|---|---|
| run_id | INTEGER (PK) | Surrogate key |
| step_name | TEXT | Nama tahap ETL (mis. `dimension::dim_customer`) |
| status | TEXT | SUCCESS / FAILED |
| row_count | INTEGER | Jumlah baris yang diproses pada tahap tersebut |
| started_at | TEXT | Waktu mulai |
| finished_at | TEXT | Waktu selesai |
| notes | TEXT | Catatan tambahan (opsional) |
