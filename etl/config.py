"""
config.py
---------
Konfigurasi terpusat untuk pipeline ETL Data Mart.
Menyimpan semua path file & konstanta agar mudah diubah tanpa menyentuh
logika ETL di modul lain (extract.py, transform.py, load.py).

Author : Muhammad Zidane Alhalita
"""

from pathlib import Path

# -----------------------------------------------------------------------------
# PATH CONFIGURATION
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
DB_DIR = PROJECT_ROOT / "db"

DB_PATH = DB_DIR / "datamart.db"
SCHEMA_SQL_PATH = SQL_DIR / "01_create_schema.sql"

# -----------------------------------------------------------------------------
# SOURCE FILES (5 source system yang berbeda -> disatukan menjadi 1 data mart)
# -----------------------------------------------------------------------------
SOURCE_FILES = {
    "crm_user_profiles": RAW_DATA_DIR / "crm_user_profiles.csv",       # CRM
    "mdm_products": RAW_DATA_DIR / "mdm_products.csv",                 # MDM
    "oms_orders": RAW_DATA_DIR / "oms_orders.csv",                     # OMS
    "web_clickstream_logs": RAW_DATA_DIR / "web_clickstream_logs.csv", # Web Analytics
    "wms_inventory_movements": RAW_DATA_DIR / "wms_inventory_movements.csv",  # WMS
}

# -----------------------------------------------------------------------------
# BUSINESS RULE LOOKUP TABLES
# Digunakan pada tahap TRANSFORM untuk membangun mini-dimension.
# -----------------------------------------------------------------------------

PAYMENT_METHOD_LOOKUP = {
    "OVO":           {"name": "OVO",                        "category": "E-Wallet"},
    "GOPAY":         {"name": "GoPay",                      "category": "E-Wallet"},
    "DANA":          {"name": "DANA",                       "category": "E-Wallet"},
    "CREDIT_CARD":   {"name": "Kartu Kredit",                "category": "Kartu Kredit"},
    "VA_BCA":        {"name": "Virtual Account - BCA",       "category": "Virtual Account"},
    "VA_MANDIRI":    {"name": "Virtual Account - Mandiri",   "category": "Virtual Account"},
}

# Pemetaan page_url ke tahapan funnel e-commerce (dipakai untuk analisis konversi)
PAGE_FUNNEL_LOOKUP = {
    "/home":            {"stage": "1. Landing",       "order": 1},
    "/search":          {"stage": "2. Discovery",     "order": 2},
    "/product/view":    {"stage": "3. Consideration", "order": 3},
    "/cart/add":        {"stage": "4. Intent",        "order": 4},
    "/checkout":        {"stage": "5. Conversion",    "order": 5},
    "/payment/success": {"stage": "6. Purchase",      "order": 6},
}

# Jenis mutasi gudang -> arah pergerakan stok (menambah / mengurangi)
INVENTORY_DIRECTION_LOOKUP = {
    "INBOUND":            1,   # barang masuk ke gudang -> menambah stok
    "RETUR_STOCK":        1,   # retur dari customer kembali ke gudang -> menambah stok
    "OUTBOUND":          -1,   # barang keluar (dikirim) -> mengurangi stok
    "ADJUSTMENT_DEFECT": -1,   # barang rusak/disesuaikan keluar -> mengurangi stok
}

STATUS_ORDER_VALUES = {
    "Delivered", "Shipped", "Cancelled", "Pending", "Processing", "Returned"
}
