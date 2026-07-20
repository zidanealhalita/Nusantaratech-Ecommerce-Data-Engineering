"""
transform.py
------------
Tahap TRANSFORM pada pipeline ETL.

Bertanggung jawab untuk:
1. Membersihkan & menstandarkan data mentah (tipe data, format tanggal, dsb).
2. Membangun seluruh tabel DIMENSI (dim_date, dim_customer, dim_product,
   dim_warehouse, dim_payment_method, dim_device, dim_page) lengkap dengan
   surrogate key yang deterministik.
3. Membangun seluruh tabel FAKTA (fact_orders, fact_inventory_movements,
   fact_web_clickstream) dengan melakukan lookup surrogate key dari dimensi
   terkait serta menghitung measure turunan (revenue, profit, signed qty, dll).

Author : Muhammad Zidane Alhalita
"""

import logging
from typing import Dict, Tuple

import pandas as pd

from etl.config import (
    PAYMENT_METHOD_LOOKUP,
    PAGE_FUNNEL_LOOKUP,
    INVENTORY_DIRECTION_LOOKUP,
)

logger = logging.getLogger("etl.transform")

DAY_NAMES_ID = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu",
}
MONTH_NAMES_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


# =============================================================================
# DIMENSION BUILDERS
# =============================================================================

def build_dim_date(min_ts: pd.Timestamp, max_ts: pd.Timestamp) -> pd.DataFrame:
    """Generate dimensi tanggal (calendar dimension) yang mencakup seluruh
    rentang tanggal yang muncul di semua source (dengan buffer 3 hari)."""
    start = (min_ts - pd.Timedelta(days=3)).normalize()
    end = (max_ts + pd.Timedelta(days=3)).normalize()
    dates = pd.date_range(start=start, end=end, freq="D")

    df = pd.DataFrame({"full_date": dates})
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["day"] = df["full_date"].dt.day
    df["day_name"] = df["full_date"].dt.day_name().map(DAY_NAMES_ID)
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["month"].map(MONTH_NAMES_ID)
    df["quarter"] = df["full_date"].dt.quarter
    df["year"] = df["full_date"].dt.year
    df["week_of_year"] = df["full_date"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = df["full_date"].dt.dayofweek.isin([5, 6]).astype(int)
    df["full_date"] = df["full_date"].dt.strftime("%Y-%m-%d")

    cols = ["date_key", "full_date", "day", "day_name", "month", "month_name",
            "quarter", "year", "week_of_year", "is_weekend"]
    logger.info("dim_date dibangun: %d baris (%s s.d. %s)", len(df), start.date(), end.date())
    return df[cols]


def build_dim_customer(crm_df: pd.DataFrame) -> pd.DataFrame:
    """Membangun dim_customer (SCD Type 1) dari data CRM."""
    df = crm_df.drop_duplicates(subset="user_id").reset_index(drop=True).copy()

    df["signup_datetime"] = pd.to_datetime(df["signup_timestamp"])
    df["signup_date"] = df["signup_datetime"].dt.strftime("%Y-%m-%d")

    load_reference_date = pd.to_datetime("2026-07-01")  # snapshot ETL run
    df["tenure_days_as_of_load"] = (load_reference_date - df["signup_datetime"]).dt.days

    df["customer_key"] = range(1, len(df) + 1)
    df["signup_datetime"] = df["signup_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

    out = df[["customer_key", "user_id", "nama_lengkap", "email", "kota",
              "account_tier", "signup_date", "signup_datetime", "tenure_days_as_of_load"]]
    logger.info("dim_customer dibangun: %d baris unik (dari %d baris mentah)", len(out), len(crm_df))
    return out


def build_dim_product(mdm_df: pd.DataFrame) -> pd.DataFrame:
    """Membangun dim_product (SCD Type 1) dari data MDM, lengkap dengan
    metrik margin yang dihitung di sisi ETL."""
    df = mdm_df.drop_duplicates(subset="product_id").reset_index(drop=True).copy()

    df["margin_idr"] = df["harga_jual_idr"] - df["harga_modal_idr"]
    df["margin_pct"] = (df["margin_idr"] / df["harga_jual_idr"] * 100).round(2)
    df["is_active"] = df["is_active"].astype(bool).astype(int)
    df["product_key"] = range(1, len(df) + 1)

    out = df[["product_key", "product_id", "nama_produk", "kategori",
              "harga_modal_idr", "harga_jual_idr", "margin_idr", "margin_pct", "is_active"]]
    logger.info("dim_product dibangun: %d baris unik", len(out))
    return out


def build_dim_warehouse(wms_df: pd.DataFrame) -> pd.DataFrame:
    """Derived dimension: mem-parsing warehouse_id (mis. 'WH-JAKARTA-01')
    menjadi nama gudang & kode gudang yang lebih mudah dibaca untuk reporting."""
    ids = sorted(wms_df["warehouse_id"].dropna().unique())
    rows = []
    for wid in ids:
        parts = wid.split("-")  # ['WH', 'JAKARTA', '01']
        name = parts[1].title() if len(parts) >= 2 else wid
        code = parts[2] if len(parts) >= 3 else ""
        rows.append({"warehouse_id": wid, "warehouse_name": name, "warehouse_code": code})

    df = pd.DataFrame(rows)
    df["warehouse_key"] = range(1, len(df) + 1)
    out = df[["warehouse_key", "warehouse_id", "warehouse_name", "warehouse_code"]]
    logger.info("dim_warehouse dibangun: %d gudang -> %s", len(out), list(out["warehouse_name"]))
    return out


def build_dim_payment_method(oms_df: pd.DataFrame) -> pd.DataFrame:
    """Mini-dimension untuk metode pembayaran, memakai lookup table bisnis
    di config.py agar nama & kategori konsisten dan mudah dipetakan."""
    codes = sorted(oms_df["metode_pembayaran"].dropna().unique())
    rows = []
    for code in codes:
        meta = PAYMENT_METHOD_LOOKUP.get(code, {"name": code, "category": "Lainnya"})
        rows.append({"payment_method_code": code,
                      "payment_method_name": meta["name"],
                      "payment_category": meta["category"]})
    df = pd.DataFrame(rows)
    df["payment_method_key"] = range(1, len(df) + 1)
    out = df[["payment_method_key", "payment_method_code", "payment_method_name", "payment_category"]]
    logger.info("dim_payment_method dibangun: %d metode pembayaran", len(out))
    return out


def build_dim_device(web_df: pd.DataFrame) -> pd.DataFrame:
    """Derived dimension: memecah device_type (mis. 'Mobile-Android')
    menjadi platform (Desktop/Mobile) dan sistem operasi."""
    codes = sorted(web_df["device_type"].dropna().unique())
    rows = []
    for code in codes:
        platform, _, os_name = code.partition("-")
        rows.append({"device_type_code": code, "platform": platform, "operating_system": os_name})
    df = pd.DataFrame(rows)
    df["device_key"] = range(1, len(df) + 1)
    out = df[["device_key", "device_type_code", "platform", "operating_system"]]
    logger.info("dim_device dibangun: %d tipe perangkat", len(out))
    return out


def build_dim_page(web_df: pd.DataFrame) -> pd.DataFrame:
    """Mini-dimension untuk halaman web, dipetakan ke tahap funnel e-commerce
    (Landing -> Discovery -> Consideration -> Intent -> Conversion -> Purchase)."""
    urls = sorted(web_df["page_url"].dropna().unique())
    rows = []
    for url in urls:
        meta = PAGE_FUNNEL_LOOKUP.get(url, {"stage": "0. Unknown", "order": 0})
        rows.append({"page_url": url, "funnel_stage": meta["stage"], "funnel_order": meta["order"]})
    df = pd.DataFrame(rows).sort_values("funnel_order").reset_index(drop=True)
    df["page_key"] = range(1, len(df) + 1)
    out = df[["page_key", "page_url", "funnel_stage", "funnel_order"]]
    logger.info("dim_page dibangun: %d halaman", len(out))
    return out


# =============================================================================
# FACT BUILDERS
# =============================================================================

def _date_key_from_series(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts).dt.strftime("%Y%m%d").astype(int)


def build_fact_orders(oms_df: pd.DataFrame, dim_customer: pd.DataFrame,
                       dim_product: pd.DataFrame, dim_payment: pd.DataFrame) -> pd.DataFrame:
    """Membangun fact_orders dengan grain 1 baris = 1 order, melakukan
    lookup surrogate key ke dim_customer / dim_product / dim_payment_method,
    serta menghitung measure revenue, cost, dan profit."""
    df = oms_df.drop_duplicates(subset="order_id").copy()

    before = len(df)
    df = df[df["user_id"].isin(dim_customer["user_id"])]
    df = df[df["product_id"].isin(dim_product["product_id"])]
    dropped = before - len(df)
    if dropped:
        logger.warning("fact_orders: %d baris dibuang karena orphan FK (user/product tidak ditemukan)", dropped)

    df["order_datetime"] = pd.to_datetime(df["order_timestamp"])
    df["date_key"] = _date_key_from_series(df["order_datetime"])

    df = df.merge(dim_customer[["user_id", "customer_key"]], on="user_id", how="left")
    df = df.merge(dim_product[["product_id", "product_key", "harga_modal_idr", "harga_jual_idr"]],
                   on="product_id", how="left")
    df = df.merge(
        dim_payment[["payment_method_code", "payment_method_key"]],
        left_on="metode_pembayaran", right_on="payment_method_code", how="left"
    )

    df["quantity"] = df["jumlah_barang"].astype(int)
    df["unit_price_idr"] = df["harga_jual_idr"].astype(int)
    df["unit_cost_idr"] = df["harga_modal_idr"].astype(int)
    df["gross_revenue_idr"] = df["quantity"] * df["unit_price_idr"]
    df["gross_cost_idr"] = df["quantity"] * df["unit_cost_idr"]
    df["gross_profit_idr"] = df["gross_revenue_idr"] - df["gross_cost_idr"]

    df["is_delivered"] = (df["status_order"] == "Delivered").astype(int)
    df["is_cancelled"] = (df["status_order"] == "Cancelled").astype(int)
    df["is_returned"] = (df["status_order"] == "Returned").astype(int)

    df["order_datetime"] = df["order_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["order_key"] = range(1, len(df) + 1)

    cols = ["order_key", "order_id", "date_key", "order_datetime", "customer_key",
            "product_key", "payment_method_key", "status_order", "quantity",
            "unit_price_idr", "unit_cost_idr", "gross_revenue_idr", "gross_cost_idr",
            "gross_profit_idr", "is_delivered", "is_cancelled", "is_returned"]
    out = df[cols]
    logger.info("fact_orders dibangun: %d baris | total revenue = Rp %s",
                len(out), f"{out['gross_revenue_idr'].sum():,.0f}")
    return out


def build_fact_inventory_movements(wms_df: pd.DataFrame, dim_product: pd.DataFrame,
                                    dim_warehouse: pd.DataFrame) -> pd.DataFrame:
    """Membangun fact_inventory_movements dengan grain 1 baris = 1 pergerakan
    stok. Menambahkan kolom signed_quantity agar SUM() langsung merepresentasikan
    perubahan stok bersih (INBOUND/RETUR bernilai +, OUTBOUND/DEFECT bernilai -)."""
    df = wms_df.drop_duplicates(subset="movement_id").copy()

    before = len(df)
    df = df[df["product_id"].isin(dim_product["product_id"])]
    dropped = before - len(df)
    if dropped:
        logger.warning("fact_inventory_movements: %d baris dibuang karena orphan FK product_id", dropped)

    df["movement_datetime"] = pd.to_datetime(df["recorded_timestamp"])
    df["date_key"] = _date_key_from_series(df["movement_datetime"])

    df = df.merge(dim_product[["product_id", "product_key"]], on="product_id", how="left")
    df = df.merge(dim_warehouse[["warehouse_id", "warehouse_key"]], on="warehouse_id", how="left")

    df["quantity_change"] = df["kuantitas_perubahan"].astype(int)
    df["direction"] = df["jenis_mutasi"].map(INVENTORY_DIRECTION_LOOKUP).fillna(0).astype(int)
    df["signed_quantity"] = df["quantity_change"] * df["direction"]

    df["movement_datetime"] = df["movement_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["movement_key"] = range(1, len(df) + 1)

    cols = ["movement_key", "movement_id", "date_key", "movement_datetime", "product_key",
            "warehouse_key", "jenis_mutasi", "operator_id", "quantity_change", "signed_quantity"]
    out = df[cols]
    logger.info("fact_inventory_movements dibangun: %d baris | net stock change = %+d unit",
                len(out), out["signed_quantity"].sum())
    return out


def build_fact_web_clickstream(web_df: pd.DataFrame, dim_customer: pd.DataFrame,
                                dim_page: pd.DataFrame, dim_device: pd.DataFrame) -> pd.DataFrame:
    """Membangun fact_web_clickstream dengan grain 1 baris = 1 page-hit.
    customer_key dibuat nullable (LEFT JOIN) untuk mengantisipasi trafik
    anonim/guest di masa depan, walau pada dataset ini semua user teridentifikasi."""
    df = web_df.drop_duplicates(subset="log_id").copy()

    df["hit_datetime"] = pd.to_datetime(df["hit_timestamp"])
    df["date_key"] = _date_key_from_series(df["hit_datetime"])

    df = df.merge(dim_customer[["user_id", "customer_key"]], on="user_id", how="left")
    df = df.merge(dim_page[["page_url", "page_key"]], on="page_url", how="left")
    df = df.merge(dim_device[["device_type_code", "device_key"]],
                   left_on="device_type", right_on="device_type_code", how="left")

    df["hit_datetime"] = df["hit_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["response_time_ms"] = df["response_time_ms"].astype(int)
    df["click_key"] = range(1, len(df) + 1)

    cols = ["click_key", "log_id", "date_key", "hit_datetime", "session_id", "customer_key",
            "page_key", "device_key", "ip_address", "response_time_ms"]
    out = df[cols]
    logger.info("fact_web_clickstream dibangun: %d baris | %d session unik",
                len(out), out["session_id"].nunique())
    return out


# =============================================================================
# ORCHESTRATOR UNTUK TAHAP TRANSFORM
# =============================================================================

def transform_all(raw: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Menjalankan seluruh proses transform dan mengembalikan dictionary
    berisi semua tabel dimensi & fakta yang siap di-load ke data mart."""
    logger.info("=== TAHAP 2/3: TRANSFORM dimulai ===")

    crm_df = raw["crm_user_profiles"]
    mdm_df = raw["mdm_products"]
    oms_df = raw["oms_orders"]
    web_df = raw["web_clickstream_logs"]
    wms_df = raw["wms_inventory_movements"]

    # --- Tentukan rentang tanggal keseluruhan untuk dim_date -----------------
    all_ts = pd.concat([
        pd.to_datetime(crm_df["signup_timestamp"]),
        pd.to_datetime(oms_df["order_timestamp"]),
        pd.to_datetime(web_df["hit_timestamp"]),
        pd.to_datetime(wms_df["recorded_timestamp"]),
    ])
    dim_date = build_dim_date(all_ts.min(), all_ts.max())

    # --- Bangun dimensi --------------------------------------------------
    dim_customer = build_dim_customer(crm_df)
    dim_product = build_dim_product(mdm_df)
    dim_warehouse = build_dim_warehouse(wms_df)
    dim_payment_method = build_dim_payment_method(oms_df)
    dim_device = build_dim_device(web_df)
    dim_page = build_dim_page(web_df)

    # --- Bangun fakta (butuh dimensi di atas untuk lookup surrogate key) --
    fact_orders = build_fact_orders(oms_df, dim_customer, dim_product, dim_payment_method)
    fact_inventory_movements = build_fact_inventory_movements(wms_df, dim_product, dim_warehouse)
    fact_web_clickstream = build_fact_web_clickstream(web_df, dim_customer, dim_page, dim_device)

    logger.info("=== TRANSFORM selesai ===")

    return {
        "dim_date": dim_date,
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_warehouse": dim_warehouse,
        "dim_payment_method": dim_payment_method,
        "dim_device": dim_device,
        "dim_page": dim_page,
        "fact_orders": fact_orders,
        "fact_inventory_movements": fact_inventory_movements,
        "fact_web_clickstream": fact_web_clickstream,
    }
