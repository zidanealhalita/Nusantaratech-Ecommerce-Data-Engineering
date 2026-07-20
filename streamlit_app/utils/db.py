"""
utils/db.py
-----------
Modul utilitas bersama untuk seluruh halaman Streamlit:
- Koneksi ke data mart SQLite (db/datamart.db) dengan caching.
- Helper untuk menjalankan query SQL dan mengembalikan pandas DataFrame (cached).
- Helper format angka (Rupiah, persentase, angka ringkas) dipakai di semua halaman.
- Palet warna & komponen UI kecil (KPI card, header halaman) yang konsisten
  dengan brand identity project (selaras dengan reports/generate_report.py).

Author : Muhammad Zidane Alhalita
"""

import sqlite3
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# PATH & KONEKSI DATABASE
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "db" / "datamart.db"


def db_is_ready() -> bool:
    """Cek apakah database data mart sudah tersedia (hasil ETL sudah dijalankan)."""
    return DB_PATH.exists()


@st.cache_resource(show_spinner=False)
def get_connection() -> sqlite3.Connection:
    """Membuka koneksi SQLite (read-only) yang di-cache sepanjang sesi app."""
    uri = f"file:{DB_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


@st.cache_data(show_spinner=False)
def run_query(sql: str, params: Optional[Sequence] = None) -> pd.DataFrame:
    """Menjalankan query SQL terhadap data mart dan mengembalikan DataFrame.
    Hasil di-cache oleh Streamlit; gunakan tombol 'Refresh Data' di sidebar
    (clear_cache()) setelah menjalankan ulang pipeline ETL agar data terbaru."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


def clear_cache() -> None:
    """Membersihkan seluruh cache query -- dipanggil saat user menekan tombol
    'Refresh Data' di sidebar, biasanya setelah ETL dijalankan ulang."""
    run_query.clear()


@st.cache_data(show_spinner=False)
def get_min_max_date() -> tuple:
    df = run_query("SELECT MIN(full_date) AS min_d, MAX(full_date) AS max_d "
                    "FROM dim_date d WHERE EXISTS (SELECT 1 FROM fact_orders fo WHERE fo.date_key = d.date_key)")
    return pd.to_datetime(df["min_d"][0]).date(), pd.to_datetime(df["max_d"][0]).date()


@st.cache_data(show_spinner=False)
def get_distinct(table: str, column: str) -> list:
    df = run_query(f"SELECT DISTINCT {column} FROM {table} ORDER BY {column}")
    return df[column].dropna().tolist()


# -----------------------------------------------------------------------------
# BRAND PALETTE  (konsisten dengan reports/generate_report.py)
# -----------------------------------------------------------------------------
NAVY = "#16233F"
GOLD = "#E8A33D"
TEAL = "#2E9C8F"
CORAL = "#E4634B"
SLATE = "#5A6B87"
BG = "#F7F6F2"
CARD_BG = "#FFFFFF"
BORDER = "#E7E4DA"

PALETTE = [NAVY, GOLD, TEAL, CORAL, SLATE, "#8E6C9E", "#C9A24B", "#4C7A9E"]

PLOTLY_LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(family="Segoe UI, Roboto, sans-serif", color=NAVY, size=13),
    title_font=dict(size=16, color=NAVY, family="Segoe UI, Roboto, sans-serif"),
    margin=dict(l=10, r=10, t=55, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)


# -----------------------------------------------------------------------------
# FORMATTING HELPERS
# -----------------------------------------------------------------------------
def fmt_rupiah(value) -> str:
    if value is None or pd.isna(value):
        return "Rp0"
    value = float(value)
    if abs(value) >= 1e9:
        return f"Rp{value/1e9:,.2f} M".replace(",", "#").replace(".", ",").replace("#", ".")
    if abs(value) >= 1e6:
        return f"Rp{value/1e6:,.1f} jt".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"Rp{value:,.0f}".replace(",", ".")


def fmt_number(value, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "0"
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(float(value)).replace(",", ".")


def fmt_pct(value, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "0%"
    return f"{value:.{decimals}f}%".replace(".", ",")


# -----------------------------------------------------------------------------
# UI COMPONENTS KECIL
# -----------------------------------------------------------------------------
def inject_base_css():
    st.markdown(f"""
        <style>
        .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1250px; }}
        [data-testid="stMetric"] {{
            background: {CARD_BG}; border: 1px solid {BORDER}; border-top: 4px solid {GOLD};
            border-radius: 10px; padding: 14px 16px 10px 16px;
        }}
        [data-testid="stMetricLabel"] {{ color: {SLATE}; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .4px;}}
        [data-testid="stMetricValue"] {{ color: {NAVY}; }}
        .page-header {{
            background: {NAVY}; color: white; padding: 22px 28px; border-radius: 12px;
            margin-bottom: 1.4rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;
        }}
        .page-header h1 {{ margin:0; font-size: 1.35rem; }}
        .page-header p {{ margin: 4px 0 0; color:#B9C2D6; font-size: .85rem; }}
        .badge-pill {{
            background:{GOLD}; color:{NAVY}; font-weight:700; font-size:.72rem;
            padding:5px 12px; border-radius: 20px;
        }}
        section[data-testid="stSidebar"] {{ background-color: {CARD_BG}; border-right: 1px solid {BORDER}; }}
        .insight-box {{
            background:{CARD_BG}; border:1px solid {BORDER}; border-left:5px solid {TEAL};
            border-radius:8px; padding:12px 16px; margin:.4rem 0; font-size:.9rem; color:{NAVY};
        }}
        </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, badge: str = "Data Mart"):
    st.markdown(f"""
        <div class="page-header">
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <span class="badge-pill">{badge}</span>
        </div>
    """, unsafe_allow_html=True)


def no_database_warning():
    st.error(
        "⚠️ **Database data mart belum ditemukan.**\n\n"
        f"File `{DB_PATH.relative_to(PROJECT_ROOT)}` tidak ada. Jalankan pipeline ETL terlebih "
        "dahulu dari root folder project:\n\n"
        "```bash\npython -m etl.run_etl\n```\n\n"
        "Setelah itu, refresh halaman ini."
    )
    st.stop()
