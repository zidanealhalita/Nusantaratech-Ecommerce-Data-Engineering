"""
run_etl.py
----------
Entry point utama untuk menjalankan seluruh pipeline ETL Data Mart secara
end-to-end: EXTRACT -> TRANSFORM -> LOAD -> DATA QUALITY CHECK.

Cara pakai:
    python -m etl.run_etl

Author : Muhammad Zidane Alhalita
"""

import logging
import sys
import time
from pathlib import Path

# Agar script bisa dijalankan langsung (python etl/run_etl.py) maupun sebagai
# module (python -m etl.run_etl), tambahkan root project ke sys.path.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from etl.extract import extract_all
from etl.transform import transform_all
from etl.load import run_load, get_connection
from etl.data_quality import run_all_checks
from etl.config import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-16s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("etl.run_etl")


def main() -> None:
    pipeline_start = time.time()
    logger.info("#############################################################")
    logger.info("#  NUSANTARATECH E-COMMERCE DATA MART - ETL PIPELINE          #")
    logger.info("#  Author: Muhammad Zidane Alhalita                          #")
    logger.info("#############################################################")

    # 1) EXTRACT --------------------------------------------------------
    raw = extract_all()

    # 2) TRANSFORM --------------------------------------------------------
    dm = transform_all(raw)

    # 3) LOAD --------------------------------------------------------
    run_load(raw, dm)

    # 4) DATA QUALITY CHECK ------------------------------------------------
    logger.info("=== TAHAP TAMBAHAN: DATA QUALITY CHECK dimulai ===")
    conn = get_connection()
    try:
        results = run_all_checks(conn)
    finally:
        conn.close()

    failed = [r for r in results if r[1] == "FAIL"]
    elapsed = time.time() - pipeline_start

    logger.info("#############################################################")
    logger.info("#  PIPELINE SELESAI dalam %.2f detik", elapsed)
    logger.info("#  Database  : %s", DB_PATH)
    logger.info("#  DQ Checks : %d PASS / %d FAIL (dari %d total)",
                 len(results) - len(failed), len(failed), len(results))
    logger.info("#############################################################")

    if failed:
        logger.warning("Terdapat %d data quality check yang FAIL. Mohon periksa log di atas.", len(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
