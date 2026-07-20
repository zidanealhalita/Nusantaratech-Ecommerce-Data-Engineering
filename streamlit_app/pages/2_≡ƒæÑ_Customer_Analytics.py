"""
pages/2_👥_Customer_Analytics.py
---------------------------------
Halaman analisis pelanggan: segmentasi account tier, top pelanggan (CLV
sederhana), distribusi pelanggan per kota, tren signup, serta identifikasi
pelanggan yang belum pernah order (kandidat kampanye reaktivasi).

Author : Muhammad Zidane Alhalita
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.db import (
    db_is_ready, no_database_warning, run_query, get_distinct,
    inject_base_css, page_header, fmt_rupiah, fmt_number, fmt_pct,
    NAVY, GOLD, TEAL, CORAL, SLATE, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(page_title="Customer Analytics | NusantaraTech", page_icon="👥", layout="wide")
inject_base_css()

if not db_is_ready():
    no_database_warning()

page_header("👥 Customer Analytics", "Segmentasi pelanggan, nilai belanja, dan peluang retensi.")

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
tiers = get_distinct("dim_customer", "account_tier")
cities = get_distinct("dim_customer", "kota")

with st.sidebar:
    st.markdown("### 🔎 Filter")
    sel_tiers = st.multiselect("Account tier", tiers, default=tiers)
    sel_cities = st.multiselect("Kota", cities, default=cities)
    st.caption("Filter berlaku untuk seluruh chart & tabel di halaman ini.")

if not (sel_tiers and sel_cities):
    st.warning("Pilih minimal 1 opsi pada setiap filter di sidebar untuk menampilkan data.")
    st.stop()


def in_clause(values):
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


CUST_WHERE = f"dc.account_tier IN {in_clause(sel_tiers)} AND dc.kota IN {in_clause(sel_cities)}"

# =============================================================================
# KPI
# =============================================================================
kpi = run_query(f"""
    SELECT
        COUNT(*) AS total_customer,
        (SELECT COUNT(DISTINCT fo.customer_key) FROM fact_orders fo
            JOIN dim_customer dc2 ON fo.customer_key = dc2.customer_key
            WHERE dc2.account_tier IN {in_clause(sel_tiers)} AND dc2.kota IN {in_clause(sel_cities)}) AS active_customer,
        ROUND(AVG(dc.tenure_days_as_of_load),0) AS avg_tenure
    FROM dim_customer dc WHERE {CUST_WHERE}
""").iloc[0]

active_rate = (kpi["active_customer"] / kpi["total_customer"] * 100) if kpi["total_customer"] else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Total Pelanggan", fmt_number(kpi["total_customer"]))
c2.metric("🛒 Pelanggan Aktif (pernah order)", fmt_number(kpi["active_customer"]), f"{active_rate:.1f}%".replace(".", ","))
c3.metric("😴 Belum Pernah Order", fmt_number(kpi["total_customer"] - kpi["active_customer"]))
c4.metric("📅 Rata-rata Tenure", f"{fmt_number(kpi['avg_tenure'])} hari")

st.divider()

# =============================================================================
# SEGMENTASI ACCOUNT TIER
# =============================================================================
colA, colB = st.columns(2)

with colA:
    st.markdown("#### Revenue per Account Tier")
    tier_df = run_query(f"""
        SELECT dc.account_tier, COUNT(DISTINCT dc.customer_key) AS pelanggan,
               COUNT(fo.order_key) AS total_order,
               COALESCE(SUM(fo.gross_revenue_idr),0) AS revenue
        FROM dim_customer dc
        LEFT JOIN fact_orders fo ON dc.customer_key = fo.customer_key
        WHERE {CUST_WHERE}
        GROUP BY dc.account_tier ORDER BY revenue DESC
    """)
    fig = px.bar(tier_df, x="account_tier", y="revenue", color="account_tier",
                 color_discrete_sequence=PALETTE, text="pelanggan")
    fig.update_traces(texttemplate="%{text} pelanggan", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False, xaxis_title=None, yaxis_title="Revenue (IDR)")
    st.plotly_chart(fig, width="stretch")

with colB:
    st.markdown("#### Distribusi Pelanggan per Kota")
    city_df = run_query(f"""
        SELECT dc.kota, COUNT(*) AS n FROM dim_customer dc WHERE {CUST_WHERE}
        GROUP BY dc.kota ORDER BY n DESC
    """)
    fig = px.pie(city_df, names="kota", values="n", hole=0.5, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False)
    st.plotly_chart(fig, width="stretch")

# =============================================================================
# TREN SIGNUP PELANGGAN
# =============================================================================
st.markdown("#### Tren Pendaftaran Pelanggan Baru (per Bulan)")
signup_df = run_query(f"""
    SELECT substr(dc.signup_date,1,7) AS bulan, COUNT(*) AS jumlah_signup
    FROM dim_customer dc WHERE {CUST_WHERE}
    GROUP BY bulan ORDER BY bulan
""")
fig = px.bar(signup_df, x="bulan", y="jumlah_signup", color_discrete_sequence=[TEAL])
fig.update_layout(**PLOTLY_LAYOUT, height=300, xaxis_title=None, yaxis_title="Jumlah Signup")
st.plotly_chart(fig, width="stretch")

# =============================================================================
# TOP 10 PELANGGAN
# =============================================================================
st.markdown("#### 🏆 Top 10 Pelanggan Berdasarkan Total Belanja (Delivered)")
top_cust = run_query(f"""
    SELECT dc.user_id, dc.nama_lengkap, dc.kota, dc.account_tier,
           COUNT(fo.order_key) AS total_order, SUM(fo.gross_revenue_idr) AS total_belanja
    FROM fact_orders fo JOIN dim_customer dc ON fo.customer_key = dc.customer_key
    WHERE {CUST_WHERE} AND fo.is_delivered = 1
    GROUP BY dc.user_id, dc.nama_lengkap, dc.kota, dc.account_tier
    ORDER BY total_belanja DESC LIMIT 10
""")
if top_cust.empty:
    st.caption("Tidak ada order Delivered pada kombinasi filter ini.")
else:
    top_cust_display = top_cust.copy()
    top_cust_display["total_belanja"] = top_cust_display["total_belanja"].apply(fmt_rupiah)
    st.dataframe(top_cust_display, width="stretch", hide_index=True)

st.divider()

# =============================================================================
# PELANGGAN YANG BELUM PERNAH ORDER (kandidat reaktivasi)
# =============================================================================
st.markdown("#### 💤 Pelanggan yang Belum Pernah Order (Kandidat Kampanye Reaktivasi)")
never_ordered = run_query(f"""
    SELECT dc.user_id, dc.nama_lengkap, dc.kota, dc.account_tier, dc.signup_date, dc.tenure_days_as_of_load
    FROM dim_customer dc
    LEFT JOIN fact_orders fo ON dc.customer_key = fo.customer_key
    WHERE {CUST_WHERE} AND fo.order_key IS NULL
    ORDER BY dc.tenure_days_as_of_load DESC
""")
st.caption(f"Ditemukan **{fmt_number(len(never_ordered))}** pelanggan pada kombinasi filter saat ini "
           f"yang sudah mendaftar namun belum pernah bertransaksi.")
with st.expander(f"📋 Lihat & unduh daftar ({len(never_ordered)} pelanggan)"):
    st.dataframe(never_ordered, width="stretch", height=350)
    st.download_button(
        "⬇️ Download CSV", never_ordered.to_csv(index=False).encode("utf-8"),
        file_name="pelanggan_belum_order.csv", mime="text/csv",
    )
