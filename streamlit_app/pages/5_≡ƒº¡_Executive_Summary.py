"""
pages/5_🧭_Executive_Summary.py
---------------------------------
Halaman ringkasan eksekutif lintas domain: menggabungkan sales (OMS), web
analytics, dan pergerakan gudang (WMS) dalam satu tampilan harian, ditujukan
untuk audiens manajemen non-teknis. Juga menampilkan kartu insight bisnis
utama secara ringkas.

Author : Muhammad Zidane Alhalita
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.db import (
    db_is_ready, no_database_warning, run_query,
    inject_base_css, page_header, fmt_rupiah, fmt_number, fmt_pct,
    NAVY, GOLD, TEAL, CORAL, SLATE, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(page_title="Executive Summary | NusantaraTech", page_icon="🧭", layout="wide")
inject_base_css()

if not db_is_ready():
    no_database_warning()

page_header("🧭 Executive Summary", "Ringkasan lintas domain (Sales × Web × Gudang) untuk pengambilan keputusan manajemen.")

# =============================================================================
# KPI RINGKASAN
# =============================================================================
kpi = run_query("""
    SELECT
        (SELECT SUM(gross_revenue_idr) FROM fact_orders) AS revenue,
        (SELECT SUM(gross_profit_idr) FROM fact_orders) AS profit,
        (SELECT COUNT(*) FROM fact_orders) AS orders,
        (SELECT COUNT(DISTINCT session_id) FROM fact_web_clickstream) AS sessions,
        (SELECT COUNT(*) FROM fact_inventory_movements) AS movements,
        (SELECT SUM(signed_quantity) FROM fact_inventory_movements) AS net_stock,
        (SELECT COUNT(*) FROM dim_customer) AS customers,
        (SELECT COUNT(DISTINCT dc.customer_key) FROM dim_customer dc
            LEFT JOIN fact_orders fo ON dc.customer_key = fo.customer_key
            WHERE fo.order_key IS NULL) AS dormant_customers
""").iloc[0]

r1 = st.columns(4)
r1[0].metric("💰 Total Revenue", fmt_rupiah(kpi["revenue"]))
r1[1].metric("📈 Total Profit", fmt_rupiah(kpi["profit"]))
r1[2].metric("🧾 Total Order", fmt_number(kpi["orders"]))
r1[3].metric("🌐 Total Web Session", fmt_number(kpi["sessions"]))

r2 = st.columns(4)
r2[0].metric("🔄 Total Mutasi Gudang", fmt_number(kpi["movements"]))
r2[1].metric("📦 Net Stock Movement", f"{'+' if kpi['net_stock'] >= 0 else ''}{fmt_number(kpi['net_stock'])} unit")
r2[2].metric("👥 Total Pelanggan", fmt_number(kpi["customers"]))
r2[3].metric("😴 Pelanggan Dormant", fmt_number(kpi["dormant_customers"]),
             f"{kpi['dormant_customers']/kpi['customers']*100:.1f}% dari total".replace(".", ","))

st.divider()

# =============================================================================
# RINGKASAN HARIAN LINTAS DOMAIN (dual-axis chart)
# =============================================================================
st.markdown("#### 📅 Ringkasan Harian: Revenue vs Aktivitas Web vs Mutasi Gudang")

daily = run_query("""
    SELECT
        d.full_date,
        COALESCE(sales.total_order, 0)       AS total_order,
        COALESCE(sales.revenue, 0)           AS revenue,
        COALESCE(web.sessions, 0)            AS web_sessions,
        COALESCE(inv.movements, 0)           AS warehouse_movements
    FROM dim_date d
    LEFT JOIN (SELECT date_key, COUNT(*) AS total_order, SUM(gross_revenue_idr) AS revenue
               FROM fact_orders GROUP BY date_key) sales ON d.date_key = sales.date_key
    LEFT JOIN (SELECT date_key, COUNT(DISTINCT session_id) AS sessions
               FROM fact_web_clickstream GROUP BY date_key) web ON d.date_key = web.date_key
    LEFT JOIN (SELECT date_key, COUNT(*) AS movements
               FROM fact_inventory_movements GROUP BY date_key) inv ON d.date_key = inv.date_key
    WHERE sales.total_order IS NOT NULL OR web.sessions IS NOT NULL OR inv.movements IS NOT NULL
    ORDER BY d.full_date
""")
daily["full_date"] = pd.to_datetime(daily["full_date"])

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Bar(x=daily["full_date"], y=daily["revenue"], name="Revenue (IDR)",
                      marker_color=GOLD, opacity=0.75), secondary_y=False)
fig.add_trace(go.Scatter(x=daily["full_date"], y=daily["web_sessions"], name="Web Sessions",
                          mode="lines+markers", line=dict(color=NAVY, width=2)), secondary_y=True)
fig.add_trace(go.Scatter(x=daily["full_date"], y=daily["warehouse_movements"], name="Mutasi Gudang",
                          mode="lines+markers", line=dict(color=CORAL, width=2, dash="dot")), secondary_y=True)
fig.update_layout(**PLOTLY_LAYOUT, height=420, legend_title=None, hovermode="x unified")
fig.update_yaxes(title_text="Revenue (IDR)", secondary_y=False)
fig.update_yaxes(title_text="Jumlah Aktivitas", secondary_y=True)
st.plotly_chart(fig, width="stretch")
st.caption(
    "💡 Chart ini menunjukkan bagaimana tiga proses bisnis berbeda (penjualan, aktivitas web, "
    "pergerakan gudang) berjalan pada tanggal yang sama — nilai nyata dari data mart terpusat "
    "dibanding harus membuka 3 sistem terpisah."
)

st.divider()

# =============================================================================
# KATEGORI: REVENUE TINGGI VS TINGKAT KERUSAKAN
# =============================================================================
st.markdown("#### ⚖️ Kategori Produk: Revenue Tinggi vs Tingkat Kerusakan Gudang")
cross_df = run_query("""
    SELECT
        dp.kategori,
        COALESCE(SUM(fo.gross_revenue_idr), 0) AS revenue,
        COALESCE(SUM(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN fim.quantity_change ELSE 0 END), 0) AS unit_rusak
    FROM dim_product dp
    LEFT JOIN fact_orders fo ON dp.product_key = fo.product_key
    LEFT JOIN fact_inventory_movements fim ON dp.product_key = fim.product_key
    GROUP BY dp.kategori
""")
fig = px.scatter(
    cross_df, x="revenue", y="unit_rusak", text="kategori", size="revenue",
    color="kategori", color_discrete_sequence=PALETTE,
)
fig.update_traces(textposition="top center")
fig.update_layout(**PLOTLY_LAYOUT, height=420, showlegend=False,
                   xaxis_title="Total Revenue (IDR)", yaxis_title="Total Unit Rusak")
st.plotly_chart(fig, width="stretch")
st.caption("💡 Kategori di kuadran kanan-atas (revenue tinggi, unit rusak tinggi) adalah kandidat "
           "utama untuk evaluasi kualitas supplier/produk.")

st.divider()

# =============================================================================
# KARTU INSIGHT BISNIS
# =============================================================================
st.markdown("#### 📝 Insight Bisnis Utama")

insight_data = run_query("""
    SELECT
        (SELECT dp.kategori FROM fact_orders fo JOIN dim_product dp ON fo.product_key = dp.product_key
            GROUP BY dp.kategori ORDER BY SUM(fo.gross_revenue_idr) DESC LIMIT 1) AS top_kategori,
        (SELECT dc.kota FROM fact_orders fo JOIN dim_customer dc ON fo.customer_key = dc.customer_key
            GROUP BY dc.kota ORDER BY SUM(fo.gross_revenue_idr) DESC LIMIT 1) AS top_kota,
        (SELECT dw.warehouse_name FROM fact_inventory_movements fim
            JOIN dim_warehouse dw ON fim.warehouse_key = dw.warehouse_key
            GROUP BY dw.warehouse_name ORDER BY SUM(fim.signed_quantity) ASC LIMIT 1) AS gudang_kritis,
        (SELECT dpm.payment_method_name FROM fact_orders fo
            JOIN dim_payment_method dpm ON fo.payment_method_key = dpm.payment_method_key
            GROUP BY dpm.payment_method_name ORDER BY COUNT(*) DESC LIMIT 1) AS metode_favorit
""").iloc[0]

ic1, ic2 = st.columns(2)
with ic1:
    st.markdown(f"""<div class="insight-box">🏆 <b>Kategori penyumbang revenue tertinggi:</b> {insight_data['top_kategori']}</div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="insight-box">🏙️ <b>Kota dengan revenue tertinggi:</b> {insight_data['top_kota']}</div>""", unsafe_allow_html=True)
with ic2:
    st.markdown(f"""<div class="insight-box">🚨 <b>Gudang dengan stok paling kritis:</b> {insight_data['gudang_kritis']}</div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="insight-box">💳 <b>Metode pembayaran favorit:</b> {insight_data['metode_favorit']}</div>""", unsafe_allow_html=True)

st.info(
    "📄 Untuk analisis lebih detail per domain, buka halaman **Sales Performance**, "
    "**Customer Analytics**, **Web Analytics**, atau **Inventory & Warehouse** melalui sidebar."
)
