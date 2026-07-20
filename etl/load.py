"""
load.py
-------
Tahap LOAD pada pipeline ETL.

Bertanggung jawab untuk:
1. Menjalankan DDL (sql/01_create_schema.sql) untuk membuat/reset seluruh
   tabel di database SQLite (staging, dimensi, fakta, audit log).
2. Memuat data mentah ke staging layer (full load, sesuai raw source).
3. Memuat seluruh tabel dimensi & fakta hasil transform ke data mart.
4. Mencatat setiap langkah ke tabel etl_run_log untuk audit trail.

Author : Muhammad Zidane Alhalita
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict

import pandas as pd

from etl.config import DB_PATH, SCHEMA_SQL_PATH

logger = logging.getLogger("etl.load")

STAGING_TABLE_MAP = {
    "crm_user_profiles": "stg_crm_user_profiles",
    "mdm_products": "stg_mdm_products",
    "oms_orders": "stg_oms_orders",
    "web_clickstream_logs": "stg_web_clickstream_logs",
    "wms_inventory_movements": "stg_wms_inventory_movements",
}

# Urutan load PENTING: dimensi harus dimuat sebelum fakta (menjaga FK integrity)
DIMENSION_LOAD_ORDER = [
    "dim_date", "dim_customer", "dim_product", "dim_warehouse",
    "dim_payment_method", "dim_device", "dim_page",
]
FACT_LOAD_ORDER = [
    "fact_orders", "fact_inventory_movements", "fact_web_clickstream",
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Menjalankan script DDL untuk membuat ulang seluruh struktur tabel."""
    logger.info("Menjalankan DDL schema dari %s", SCHEMA_SQL_PATH)
    with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
        ddl_script = f.read()
    conn.executescript(ddl_script)
    conn.commit()
    logger.info("Schema berhasil dibuat/direset.")


def _log_run(conn: sqlite3.Connection, step_name: str, status: str,
             row_count: int, started_at: datetime, notes: str = "") -> None:
    conn.execute(
        """INSERT INTO etl_run_log (step_name, status, row_count, started_at, finished_at, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (step_name, status, row_count, started_at.strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), notes)
    )
    conn.commit()


def load_staging(conn: sqlite3.Connection, raw: Dict[str, pd.DataFrame]) -> None:
    """Full-load data mentah ke staging layer (schema-on-read, 1:1 dengan CSV sumber)."""
    logger.info("--- Loading staging layer ---")
    for source_name, df in raw.items():
        table = STAGING_TABLE_MAP[source_name]
        started = datetime.now()
        df.to_sql(table, conn, if_exists="append", index=False)
        _log_run(conn, f"staging::{table}", "SUCCESS", len(df), started)
        logger.info("  -> %-30s : %5d baris ter-load", table, len(df))


def load_data_mart(conn: sqlite3.Connection, dm: Dict[str, pd.DataFrame]) -> None:
    """Load seluruh tabel dimensi lalu fakta ke dalam data mart (urutan menjaga FK)."""
    logger.info("--- Loading dimension tables ---")
    for name in DIMENSION_LOAD_ORDER:
        df = dm[name]
        started = datetime.now()
        df.to_sql(name, conn, if_exists="append", index=False)
        _log_run(conn, f"dimension::{name}", "SUCCESS", len(df), started)
        logger.info("  -> %-25s : %5d baris ter-load", name, len(df))

    logger.info("--- Loading fact tables ---")
    for name in FACT_LOAD_ORDER:
        df = dm[name]
        started = datetime.now()
        df.to_sql(name, conn, if_exists="append", index=False)
        _log_run(conn, f"fact::{name}", "SUCCESS", len(df), started)
        logger.info("  -> %-25s : %5d baris ter-load", name, len(df))


def run_load(raw: Dict[str, pd.DataFrame], dm: Dict[str, pd.DataFrame]) -> None:
    """Orchestrator tahap LOAD: create schema -> load staging -> load data mart."""
    logger.info("=== TAHAP 3/3: LOAD dimulai ===")
    conn = get_connection()
    try:
        create_schema(conn)
        load_staging(conn, raw)
        load_data_mart(conn, dm)
        logger.info("=== LOAD selesai. Database tersimpan di: %s ===", DB_PATH)
    finally:
        conn.close()
