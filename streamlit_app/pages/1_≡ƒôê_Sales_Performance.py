"""
pages/1_📈_Sales_Performance.py
--------------------------------
Halaman analisis performa penjualan: KPI, tren revenue, revenue per kategori/
kota/metode pembayaran, top produk terlaris, dan distribusi status order.
Dilengkapi filter interaktif (rentang tanggal, kategori, kota, metode
pembayaran, status order).

Author : Muhammad Zidane Alhalita
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.db import (
    db_is_ready, no_database_warning, run_query, get_min_max_date, get_distinct,
    inject_base_css, page_header, fmt_rupiah, fmt_number, fmt_pct,
    NAVY, GOLD, TEAL, CORAL, SLATE, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(page_title="Sales Performance | NusantaraTech", page_icon="📈", layout="wide")
inject_base_css()

if not db_is_ready():
    no_database_warning()

page_header("📈 Sales Performance", "Analisis revenue, profit, produk terlaris, dan fulfilment order.")

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
min_d, max_d = get_min_max_date()
categories = get_distinct("dim_product", "kategori")
cities = get_distinct("dim_customer", "kota")
payments = get_distinct("dim_payment_method", "payment_method_name")
statuses = get_distinct("fact_orders", "status_order")

with st.sidebar:
    st.markdown("### 🔎 Filter")
    date_range = st.date_input("Rentang tanggal order", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    sel_categories = st.multiselect("Kategori produk", categories, default=categories)
    sel_cities = st.multiselect("Kota pelanggan", cities, default=cities)
    sel_payments = st.multiselect("Metode pembayaran", payments, default=payments)
    sel_statuses = st.multiselect("Status order", statuses, default=statuses)
    st.caption("Filter berlaku untuk seluruh chart & tabel di halaman ini.")

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_d, max_d

if not (sel_categories and sel_cities and sel_payments and sel_statuses):
    st.warning("Pilih minimal 1 opsi pada setiap filter di sidebar untuk menampilkan data.")
    st.stop()


def in_clause(values):
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


WHERE = f"""
    d.full_date BETWEEN '{start_date}' AND '{end_date}'
    AND dp.kategori IN {in_clause(sel_categories)}
    AND dc.kota IN {in_clause(sel_cities)}
    AND dpm.payment_method_name IN {in_clause(sel_payments)}
    AND fo.status_order IN {in_clause(sel_statuses)}
"""

BASE_JOIN = """
    FROM fact_orders fo
    JOIN dim_date d ON fo.date_key = d.date_key
    JOIN dim_product dp ON fo.product_key = dp.product_key
    JOIN dim_customer dc ON fo.customer_key = dc.customer_key
    JOIN dim_payment_method dpm ON fo.payment_method_key = dpm.payment_method_key
"""

# =============================================================================
# KPI
# =============================================================================
kpi = run_query(f"""
    SELECT COUNT(*) AS total_order, SUM(fo.quantity) AS total_unit,
           SUM(fo.gross_revenue_idr) AS revenue, SUM(fo.gross_profit_idr) AS profit,
           ROUND(SUM(fo.is_delivered)*100.0/COUNT(*),1) AS delivered_rate,
           ROUND(SUM(fo.is_cancelled)*100.0/COUNT(*),1) AS cancelled_rate
    {BASE_JOIN} WHERE {WHERE}
""")

if kpi.empty or kpi["total_order"][0] == 0:
    st.info("Tidak ada data pada kombinasi filter ini. Coba perluas filter di sidebar.")
    st.stop()

k = kpi.iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Revenue", fmt_rupiah(k["revenue"]))
c2.metric("📈 Profit", fmt_rupiah(k["profit"]), f"Margin {k['profit']/k['revenue']*100:.1f}%".replace(".", ","))
c3.metric("🧾 Total Order", fmt_number(k["total_order"]))
c4.metric("✅ Delivered Rate", fmt_pct(k["delivered_rate"]))
c5.metric("❌ Cancelled Rate", fmt_pct(k["cancelled_rate"]))

st.divider()

# =============================================================================
# TREN REVENUE HARIAN
# =============================================================================
st.markdown("#### Tren Revenue & Profit Harian")
trend = run_query(f"""
    SELECT d.full_date, SUM(fo.gross_revenue_idr) AS revenue, SUM(fo.gross_profit_idr) AS profit
    {BASE_JOIN} WHERE {WHERE}
    GROUP BY d.full_date ORDER BY d.full_date
""")
trend["full_date"] = pd.to_datetime(trend["full_date"])
fig = px.line(trend, x="full_date", y=["revenue", "profit"], markers=True,
              color_discrete_map={"revenue": NAVY, "profit": TEAL})
fig.update_layout(**PLOTLY_LAYOUT, height=340, xaxis_title=None, yaxis_title="IDR",
                   legend_title=None)
st.plotly_chart(fig, width="stretch")

# =============================================================================
# REVENUE PER KATEGORI & KOTA
# =============================================================================
colA, colB = st.columns(2)

with colA:
    st.markdown("#### Revenue per Kategori Produk")
    cat = run_query(f"""
        SELECT dp.kategori, SUM(fo.gross_revenue_idr) AS revenue
        {BASE_JOIN} WHERE {WHERE}
        GROUP BY dp.kategori ORDER BY revenue DESC
    """)
    fig = px.bar(cat, x="revenue", y="kategori", orientation="h", color="kategori",
                 color_discrete_sequence=PALETTE, text="revenue")
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False,
                       yaxis={"categoryorder": "total ascending"}, xaxis_title="Revenue (IDR)", yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

with colB:
    st.markdown("#### Revenue per Kota Pelanggan")
    city = run_query(f"""
        SELECT dc.kota, SUM(fo.gross_revenue_idr) AS revenue, COUNT(DISTINCT dc.customer_key) AS pelanggan
        {BASE_JOIN} WHERE {WHERE}
        GROUP BY dc.kota ORDER BY revenue DESC
    """)
    fig = px.bar(city, x="revenue", y="kota", orientation="h", color="kota",
                 color_discrete_sequence=PALETTE, text="revenue")
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False,
                       yaxis={"categoryorder": "total ascending"}, xaxis_title="Revenue (IDR)", yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

# =============================================================================
# STATUS ORDER & METODE PEMBAYARAN
# =============================================================================
colC, colD = st.columns(2)

with colC:
    st.markdown("#### Distribusi Status Order")
    status_df = run_query(f"""
        SELECT fo.status_order, COUNT(*) AS n
        {BASE_JOIN} WHERE {WHERE}
        GROUP BY fo.status_order ORDER BY n DESC
    """)
    fig = px.pie(status_df, names="status_order", values="n", hole=0.5, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False)
    st.plotly_chart(fig, width="stretch")

with colD:
    st.markdown("#### Revenue per Metode Pembayaran")
    pay_df = run_query(f"""
        SELECT dpm.payment_method_name, SUM(fo.gross_revenue_idr) AS revenue, COUNT(*) AS n_order
        {BASE_JOIN} WHERE {WHERE}
        GROUP BY dpm.payment_method_name ORDER BY revenue DESC
    """)
    fig = px.bar(pay_df, x="payment_method_name", y="revenue", color="payment_method_name",
                 color_discrete_sequence=PALETTE, text="n_order")
    fig.update_traces(texttemplate="%{text} order", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False,
                       xaxis_title=None, yaxis_title="Revenue (IDR)")
    st.plotly_chart(fig, width="stretch")

# =============================================================================
# TOP 10 PRODUK TERLARIS
# =============================================================================
st.markdown("#### 🏆 Top 10 Produk Terlaris (Delivered)")
top_products = run_query(f"""
    SELECT dp.nama_produk, dp.kategori, SUM(fo.quantity) AS total_unit,
           SUM(fo.gross_revenue_idr) AS revenue, SUM(fo.gross_profit_idr) AS profit
    {BASE_JOIN} WHERE {WHERE} AND fo.is_delivered = 1
    GROUP BY dp.nama_produk, dp.kategori ORDER BY revenue DESC LIMIT 10
""")
if top_products.empty:
    st.caption("Tidak ada order Delivered pada kombinasi filter ini.")
else:
    fig = px.bar(top_products.iloc[::-1], x="revenue", y="nama_produk", orientation="h",
                 color="kategori", color_discrete_sequence=PALETTE, text="revenue")
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=420, xaxis_title="Revenue (IDR)", yaxis_title=None,
                       legend_title="Kategori")
    st.plotly_chart(fig, width="stretch")

# =============================================================================
# TABEL DETAIL + DOWNLOAD
# =============================================================================
with st.expander("📋 Lihat & unduh data order (hasil filter saat ini)"):
    detail = run_query(f"""
        SELECT fo.order_id, d.full_date AS tanggal, dc.nama_lengkap, dc.kota, dp.nama_produk,
               dp.kategori, dpm.payment_method_name, fo.status_order, fo.quantity,
               fo.gross_revenue_idr, fo.gross_profit_idr
        {BASE_JOIN} WHERE {WHERE}
        ORDER BY d.full_date DESC LIMIT 2000
    """)
    st.dataframe(detail, width="stretch", height=380)
    st.download_button(
        "⬇️ Download CSV", detail.to_csv(index=False).encode("utf-8"),
        file_name="sales_detail_filtered.csv", mime="text/csv",
    )
