"""
Home.py
-------
Entry point aplikasi Streamlit multipage untuk NusantaraTech E-Commerce Data Mart.
Halaman ini menampilkan ringkasan umum (overview) seluruh data mart serta
navigasi ke 5 halaman analisis lainnya (lihat folder pages/).

Cara pakai:
    streamlit run streamlit_app/Home.py

Author : Muhammad Zidane Alhalita
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent))
from utils.db import (
    db_is_ready, no_database_warning, run_query, clear_cache,
    inject_base_css, page_header, fmt_rupiah, fmt_number, fmt_pct,
    NAVY, GOLD, TEAL, CORAL, SLATE, BG, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(
    page_title="NusantaraTech Data Mart | Home",
    page_icon="🏬",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_base_css()

# --- Sidebar ------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏬 NusantaraTech")
    st.caption("E-Commerce Data Mart · Streamlit Dashboard")
    st.divider()
    st.markdown(
        "**Navigasi:** gunakan menu halaman di atas ⬆️ untuk membuka analisis "
        "Sales, Customer, Web Analytics, Inventory, dan Executive Summary."
    )
    st.divider()
    if st.button("🔄 Refresh Data", width="stretch",
                  help="Bersihkan cache & baca ulang data mart (jalankan setelah ETL diulang)"):
        clear_cache()
        st.rerun()
    st.caption("Dibuat oleh **Muhammad Zidane Alhalita**")

if not db_is_ready():
    no_database_warning()

page_header(
    "🏬 NusantaraTech E-Commerce — Data Mart Overview",
    "Konsolidasi data dari 5 sistem sumber: CRM · MDM · OMS · WMS · Web Analytics",
    badge="🟢 Live dari SQLite",
)

# =============================================================================
# RINGKASAN SUMBER DATA
# =============================================================================
st.subheader("📂 Sumber Data yang Terintegrasi")
src_counts = run_query("""
    SELECT 'CRM (dim_customer)' AS sumber, COUNT(*) AS baris FROM dim_customer
    UNION ALL SELECT 'MDM (dim_product)', COUNT(*) FROM dim_product
    UNION ALL SELECT 'OMS (fact_orders)', COUNT(*) FROM fact_orders
    UNION ALL SELECT 'WMS (fact_inventory_movements)', COUNT(*) FROM fact_inventory_movements
    UNION ALL SELECT 'Web Analytics (fact_web_clickstream)', COUNT(*) FROM fact_web_clickstream
""")
cols = st.columns(5)
icons = ["👤", "📦", "🧾", "🏭", "🌐"]
for c, (_, row), icon in zip(cols, src_counts.iterrows(), icons):
    with c:
        st.metric(f"{icon} {row['sumber']}", fmt_number(row['baris']) + " baris")

st.divider()

# =============================================================================
# KPI UTAMA
# =============================================================================
st.subheader("📊 Ringkasan KPI Bisnis")

kpi = run_query("""
    SELECT
        (SELECT SUM(gross_revenue_idr) FROM fact_orders)                          AS total_revenue,
        (SELECT SUM(gross_profit_idr) FROM fact_orders)                           AS total_profit,
        (SELECT COUNT(*) FROM fact_orders)                                        AS total_orders,
        (SELECT AVG(gross_revenue_idr) FROM fact_orders)                          AS aov,
        (SELECT COUNT(*) FROM dim_customer)                                       AS total_customers,
        (SELECT COUNT(DISTINCT session_id) FROM fact_web_clickstream)             AS total_sessions,
        (SELECT ROUND(SUM(is_delivered)*100.0/COUNT(*),1) FROM fact_orders)       AS delivered_rate,
        (SELECT SUM(signed_quantity) FROM fact_inventory_movements)               AS net_stock
""").iloc[0]

r1 = st.columns(4)
r1[0].metric("💰 Total Revenue", fmt_rupiah(kpi["total_revenue"]))
r1[1].metric("📈 Total Profit", fmt_rupiah(kpi["total_profit"]),
             f"Margin {kpi['total_profit']/kpi['total_revenue']*100:.1f}%".replace(".", ","))
r1[2].metric("🧾 Total Order", fmt_number(kpi["total_orders"]),
             f"AOV {fmt_rupiah(kpi['aov'])}")
r1[3].metric("✅ Delivered Rate", fmt_pct(kpi["delivered_rate"]))

r2 = st.columns(4)
r2[0].metric("👥 Total Pelanggan", fmt_number(kpi["total_customers"]))
r2[1].metric("🌐 Web Sessions", fmt_number(kpi["total_sessions"]))
r2[2].metric("📦 Net Stock Movement", f"{'+' if kpi['net_stock'] >= 0 else ''}{fmt_number(kpi['net_stock'])} unit")
r2[3].metric("🗓️ Periode Data", "Jun 2026")

st.divider()

# =============================================================================
# TREN REVENUE HARIAN + KOMPOSISI KATEGORI (preview singkat)
# =============================================================================
left, right = st.columns([1.4, 1])

with left:
    st.markdown("##### Tren Revenue Harian")
    daily = run_query("""
        SELECT d.full_date, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_date d ON fo.date_key = d.date_key
        GROUP BY d.full_date ORDER BY d.full_date
    """)
    daily["full_date"] = pd.to_datetime(daily["full_date"])
    fig = px.area(daily, x="full_date", y="revenue")
    fig.update_traces(line_color=NAVY, fillcolor="rgba(232,163,61,0.28)")
    fig.update_layout(**PLOTLY_LAYOUT, height=320, xaxis_title=None, yaxis_title="Revenue (IDR)")
    st.plotly_chart(fig, width="stretch")
    st.caption("💡 Lihat detail lengkap & filter interaktif di halaman **Sales Performance**.")

with right:
    st.markdown("##### Revenue per Kategori")
    cat = run_query("""
        SELECT dp.kategori, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_product dp ON fo.product_key = dp.product_key
        GROUP BY dp.kategori ORDER BY revenue DESC
    """)
    fig2 = px.pie(cat, names="kategori", values="revenue", hole=0.5,
                   color_discrete_sequence=PALETTE)
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    fig2.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
    st.plotly_chart(fig2, width="stretch")

st.divider()

# =============================================================================
# PETA NAVIGASI HALAMAN
# =============================================================================
st.subheader("🧭 Jelajahi Dashboard")
nav = st.columns(5)
nav_items = [
    ("📈", "Sales Performance", "Revenue, profit, produk terlaris, status order, metode pembayaran."),
    ("👥", "Customer Analytics", "Segmentasi tier, top pelanggan, retensi & aktivasi."),
    ("🌐", "Web Analytics", "Funnel konversi, device, performa halaman."),
    ("📦", "Inventory & Warehouse", "Posisi stok, mutasi gudang, produk rusak."),
    ("🧭", "Executive Summary", "Ringkasan lintas domain untuk manajemen."),
]
for c, (icon, title, desc) in zip(nav, nav_items):
    with c:
        st.markdown(f"**{icon} {title}**")
        st.caption(desc)

st.info(
    "📌 Gunakan **menu di sidebar (kiri atas)** untuk berpindah antar halaman. "
    "Setiap halaman memiliki filter interaktif (tanggal, kategori, kota, dsb.) yang independen."
)
