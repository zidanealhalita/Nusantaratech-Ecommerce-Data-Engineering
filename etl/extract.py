"""
extract.py
----------
Tahap EXTRACT pada pipeline ETL.

Bertanggung jawab untuk:
1. Membaca file CSV mentah dari 5 source system (CRM, MDM, OMS, WMS, Web Analytics).
2. Melakukan validasi ringan (file ada, tidak kosong, kolom sesuai ekspektasi).
3. Mengembalikan dictionary of pandas DataFrame untuk diteruskan ke tahap transform.

Author : Muhammad Zidane Alhalita
"""

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

from etl.config import SOURCE_FILES

logger = logging.getLogger("etl.extract")

# Skema kolom yang diharapkan ada pada tiap source, untuk validasi cepat
EXPECTED_COLUMNS = {
    "crm_user_profiles": [
        "user_id", "nama_lengkap", "email", "kota", "account_tier", "signup_timestamp"
    ],
    "mdm_products": [
        "product_id", "nama_produk", "kategori", "harga_modal_idr", "harga_jual_idr", "is_active"
    ],
    "oms_orders": [
        "order_id", "user_id", "product_id", "jumlah_barang", "order_timestamp",
        "metode_pembayaran", "status_order"
    ],
    "web_clickstream_logs": [
        "log_id", "session_id", "user_id", "hit_timestamp", "page_url",
        "ip_address", "device_type", "response_time_ms"
    ],
    "wms_inventory_movements": [
        "movement_id", "product_id", "warehouse_id", "jenis_mutasi",
        "kuantitas_perubahan", "recorded_timestamp", "operator_id"
    ],
}


def _read_csv(name: str, path: Path) -> pd.DataFrame:
    """Membaca satu file CSV dan memvalidasi kolomnya."""
    if not path.exists():
        raise FileNotFoundError(f"[EXTRACT] Source file tidak ditemukan: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(f"[EXTRACT] Source '{name}' kosong (0 baris): {path}")

    missing_cols = set(EXPECTED_COLUMNS[name]) - set(df.columns)
    if missing_cols:
        raise ValueError(f"[EXTRACT] Source '{name}' kehilangan kolom: {missing_cols}")

    logger.info("Extract '%-25s' -> %5d baris, %2d kolom | file: %s",
                name, len(df), len(df.columns), path.name)
    return df


def extract_all() -> Dict[str, pd.DataFrame]:
    """
    Mengekstrak seluruh source file yang terdaftar pada SOURCE_FILES.

    Returns
    -------
    dict[str, pd.DataFrame]
        key   = nama source (mis. 'crm_user_profiles')
        value = DataFrame berisi data mentah (raw)
    """
    logger.info("=== TAHAP 1/3: EXTRACT dimulai ===")
    raw_data = {}
    for name, path in SOURCE_FILES.items():
        raw_data[name] = _read_csv(name, path)
    logger.info("=== EXTRACT selesai: %d source berhasil dibaca ===", len(raw_data))
    return raw_data
