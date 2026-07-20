"""
data_quality.py
----------------
Modul validasi kualitas data (Data Quality / DQ checks) yang dijalankan
SETELAH proses load selesai. Semua check memakai SQL langsung ke SQLite
untuk memastikan data mart benar-benar valid dan siap dipakai reporting.

Kategori check:
1. Row-count reconciliation : jumlah baris source vs staging vs fact/dim.
2. Referential integrity    : tidak ada baris fakta dengan FK yang orphan (NULL).
3. Uniqueness               : primary key / natural key tidak duplikat.
4. Business rule sanity     : nilai measure masuk akal (non-negatif, dsb).

Author : Muhammad Zidane Alhalita
"""

import logging
import sqlite3
from typing import List, Tuple

logger = logging.getLogger("etl.data_quality")


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    return conn.execute(query).fetchone()[0]


def run_all_checks(conn: sqlite3.Connection) -> List[Tuple[str, str, str]]:
    """
    Menjalankan seluruh DQ check dan mengembalikan list hasil:
    [(nama_check, status ('PASS'/'FAIL'), detail), ...]
    """
    results: List[Tuple[str, str, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        status = "PASS" if condition else "FAIL"
        results.append((name, status, detail))
        log_fn = logger.info if condition else logger.warning
        log_fn("[DQ %s] %-45s | %s", status, name, detail)

    # 1) Row-count reconciliation staging vs source dimensions/facts --------
    n_stg_crm = _scalar(conn, "SELECT COUNT(*) FROM stg_crm_user_profiles")
    n_dim_customer = _scalar(conn, "SELECT COUNT(*) FROM dim_customer")
    check("row_count_customer_staging_vs_dim", n_stg_crm == n_dim_customer,
          f"staging={n_stg_crm}, dim_customer={n_dim_customer}")

    n_stg_product = _scalar(conn, "SELECT COUNT(*) FROM stg_mdm_products")
    n_dim_product = _scalar(conn, "SELECT COUNT(*) FROM dim_product")
    check("row_count_product_staging_vs_dim", n_stg_product == n_dim_product,
          f"staging={n_stg_product}, dim_product={n_dim_product}")

    n_stg_orders = _scalar(conn, "SELECT COUNT(*) FROM stg_oms_orders")
    n_fact_orders = _scalar(conn, "SELECT COUNT(*) FROM fact_orders")
    check("row_count_orders_staging_vs_fact", n_stg_orders == n_fact_orders,
          f"staging={n_stg_orders}, fact_orders={n_fact_orders}")

    n_stg_wms = _scalar(conn, "SELECT COUNT(*) FROM stg_wms_inventory_movements")
    n_fact_wms = _scalar(conn, "SELECT COUNT(*) FROM fact_inventory_movements")
    check("row_count_inventory_staging_vs_fact", n_stg_wms == n_fact_wms,
          f"staging={n_stg_wms}, fact_inventory_movements={n_fact_wms}")

    n_stg_web = _scalar(conn, "SELECT COUNT(*) FROM stg_web_clickstream_logs")
    n_fact_web = _scalar(conn, "SELECT COUNT(*) FROM fact_web_clickstream")
    check("row_count_clickstream_staging_vs_fact", n_stg_web == n_fact_web,
          f"staging={n_stg_web}, fact_web_clickstream={n_fact_web}")

    # 2) Referential integrity: FK tidak boleh NULL/orphan -------------------
    orphan_fo_customer = _scalar(conn, "SELECT COUNT(*) FROM fact_orders WHERE customer_key IS NULL")
    check("fk_integrity_fact_orders_customer", orphan_fo_customer == 0, f"orphan_rows={orphan_fo_customer}")

    orphan_fo_product = _scalar(conn, "SELECT COUNT(*) FROM fact_orders WHERE product_key IS NULL")
    check("fk_integrity_fact_orders_product", orphan_fo_product == 0, f"orphan_rows={orphan_fo_product}")

    orphan_fo_payment = _scalar(conn, "SELECT COUNT(*) FROM fact_orders WHERE payment_method_key IS NULL")
    check("fk_integrity_fact_orders_payment", orphan_fo_payment == 0, f"orphan_rows={orphan_fo_payment}")

    orphan_inv_product = _scalar(conn, "SELECT COUNT(*) FROM fact_inventory_movements WHERE product_key IS NULL")
    check("fk_integrity_fact_inventory_product", orphan_inv_product == 0, f"orphan_rows={orphan_inv_product}")

    orphan_inv_wh = _scalar(conn, "SELECT COUNT(*) FROM fact_inventory_movements WHERE warehouse_key IS NULL")
    check("fk_integrity_fact_inventory_warehouse", orphan_inv_wh == 0, f"orphan_rows={orphan_inv_wh}")

    orphan_click_page = _scalar(conn, "SELECT COUNT(*) FROM fact_web_clickstream WHERE page_key IS NULL")
    check("fk_integrity_fact_clickstream_page", orphan_click_page == 0, f"orphan_rows={orphan_click_page}")

    orphan_click_device = _scalar(conn, "SELECT COUNT(*) FROM fact_web_clickstream WHERE device_key IS NULL")
    check("fk_integrity_fact_clickstream_device", orphan_click_device == 0, f"orphan_rows={orphan_click_device}")

    # 3) Uniqueness natural key / degenerate key ------------------------------
    dup_orders = _scalar(conn, """
        SELECT COUNT(*) FROM (SELECT order_id FROM fact_orders GROUP BY order_id HAVING COUNT(*) > 1)
    """)
    check("uniqueness_fact_orders_order_id", dup_orders == 0, f"duplicate_order_id={dup_orders}")

    dup_customer = _scalar(conn, """
        SELECT COUNT(*) FROM (SELECT user_id FROM dim_customer GROUP BY user_id HAVING COUNT(*) > 1)
    """)
    check("uniqueness_dim_customer_user_id", dup_customer == 0, f"duplicate_user_id={dup_customer}")

    # 4) Business rule sanity checks -----------------------------------------
    negative_revenue = _scalar(conn, "SELECT COUNT(*) FROM fact_orders WHERE gross_revenue_idr < 0")
    check("business_rule_no_negative_revenue", negative_revenue == 0, f"negative_rows={negative_revenue}")

    negative_qty = _scalar(conn, "SELECT COUNT(*) FROM fact_orders WHERE quantity <= 0")
    check("business_rule_positive_quantity", negative_qty == 0, f"invalid_rows={negative_qty}")

    invalid_margin = _scalar(conn, "SELECT COUNT(*) FROM dim_product WHERE margin_idr < 0")
    check("business_rule_non_negative_margin", invalid_margin == 0, f"negative_margin_products={invalid_margin}")

    n_passed = sum(1 for r in results if r[1] == "PASS")
    logger.info("=== DATA QUALITY SUMMARY: %d/%d check PASS ===", n_passed, len(results))
    return results
