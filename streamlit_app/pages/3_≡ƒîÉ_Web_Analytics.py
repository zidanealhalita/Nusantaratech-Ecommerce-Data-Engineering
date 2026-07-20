"""
pages/3_🌐_Web_Analytics.py
-----------------------------
Halaman analisis aktivitas web: funnel konversi, distribusi device/platform,
performa response time per halaman, dan conversion rate (browse-to-buy) per
kota pelanggan.

Author : Muhammad Zidane Alhalita
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.db import (
    db_is_ready, no_database_warning, run_query, get_distinct,
    inject_base_css, page_header, fmt_number, fmt_pct,
    NAVY, GOLD, TEAL, CORAL, SLATE, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(page_title="Web Analytics | NusantaraTech", page_icon="🌐", layout="wide")
inject_base_css()

if not db_is_ready():
    no_database_warning()

page_header("🌐 Web Analytics & Conversion Funnel", "Perilaku pengunjung website dari landing hingga pembayaran berhasil.")

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
platforms = get_distinct("dim_device", "platform")

with st.sidebar:
    st.markdown("### 🔎 Filter")
    sel_platforms = st.multiselect("Platform", platforms, default=platforms)
    st.caption("Filter berlaku untuk seluruh chart di halaman ini.")

if not sel_platforms:
    st.warning("Pilih minimal 1 platform di sidebar untuk menampilkan data.")
    st.stop()


def in_clause(values):
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


WHERE = f"dd.platform IN {in_clause(sel_platforms)}"
JOIN = """
    FROM fact_web_clickstream fwc
    JOIN dim_device dd ON fwc.device_key = dd.device_key
    JOIN dim_page dpg ON fwc.page_key = dpg.page_key
"""

# =============================================================================
# KPI
# =============================================================================
kpi = run_query(f"""
    SELECT COUNT(*) AS total_hit, COUNT(DISTINCT fwc.session_id) AS total_session,
           ROUND(AVG(fwc.response_time_ms),0) AS avg_response
    {JOIN} WHERE {WHERE}
""").iloc[0]

c1, c2, c3 = st.columns(3)
c1.metric("👆 Total Page Hit", fmt_number(kpi["total_hit"]))
c2.metric("🧭 Unique Session", fmt_number(kpi["total_session"]))
c3.metric("⏱️ Rata-rata Response Time", f"{fmt_number(kpi['avg_response'])} ms")

st.divider()

# =============================================================================
# FUNNEL KONVERSI
# =============================================================================
st.markdown("#### 🪜 Funnel Konversi (Unique Session per Tahap)")
funnel_df = run_query(f"""
    SELECT dpg.funnel_order, dpg.funnel_stage, COUNT(DISTINCT fwc.session_id) AS sessions
    {JOIN} WHERE {WHERE}
    GROUP BY dpg.funnel_order, dpg.funnel_stage ORDER BY dpg.funnel_order
""")
fig = go.Figure(go.Funnel(
    y=funnel_df["funnel_stage"], x=funnel_df["sessions"],
    marker={"color": PALETTE[:len(funnel_df)]},
    textinfo="value+percent initial",
))
fig.update_layout(**PLOTLY_LAYOUT, height=420)
st.plotly_chart(fig, width="stretch")
st.caption(
    "💡 Funnel dihitung dari `dim_page.funnel_order` (1=Landing hingga 6=Purchase). "
    "Karena ini adalah data sintetis, drop-off antar tahap tidak selalu monoton menurun."
)

st.divider()

# =============================================================================
# DEVICE & RESPONSE TIME
# =============================================================================
colA, colB = st.columns(2)

with colA:
    st.markdown("#### Distribusi Trafik per Device")
    dev_df = run_query(f"""
        SELECT dd.device_type_code, COUNT(*) AS n
        {JOIN} WHERE {WHERE}
        GROUP BY dd.device_type_code ORDER BY n DESC
    """)
    fig = px.pie(dev_df, names="device_type_code", values="n", hole=0.5, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False)
    st.plotly_chart(fig, width="stretch")

with colB:
    st.markdown("#### Rata-rata Response Time per Halaman")
    resp_df = run_query(f"""
        SELECT dpg.page_url, ROUND(AVG(fwc.response_time_ms),0) AS avg_response
        {JOIN} WHERE {WHERE}
        GROUP BY dpg.page_url ORDER BY avg_response DESC
    """)
    fig = px.bar(resp_df, x="avg_response", y="page_url", orientation="h",
                 color="page_url", color_discrete_sequence=PALETTE, text="avg_response")
    fig.update_traces(texttemplate="%{text:.0f} ms", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False,
                       yaxis={"categoryorder": "total ascending"}, xaxis_title="ms", yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

st.divider()

# =============================================================================
# CONVERSION RATE PER KOTA (browse -> buy)
# =============================================================================
st.markdown("#### 🎯 Conversion Rate per Kota (Visitor → Buyer)")
conv_df = run_query(f"""
    SELECT dc.kota,
        COUNT(DISTINCT fwc.customer_key) AS visitor,
        COUNT(DISTINCT CASE WHEN fo.order_key IS NOT NULL THEN fwc.customer_key END) AS buyer,
        ROUND(COUNT(DISTINCT CASE WHEN fo.order_key IS NOT NULL THEN fwc.customer_key END) * 100.0
              / NULLIF(COUNT(DISTINCT fwc.customer_key), 0), 2) AS conversion_rate_pct
    FROM fact_web_clickstream fwc
    JOIN dim_device dd ON fwc.device_key = dd.device_key
    JOIN dim_customer dc ON fwc.customer_key = dc.customer_key
    LEFT JOIN fact_orders fo ON fo.customer_key = fwc.customer_key
    WHERE {WHERE}
    GROUP BY dc.kota ORDER BY conversion_rate_pct DESC
""")
fig = px.bar(conv_df, x="kota", y="conversion_rate_pct", color="kota",
             color_discrete_sequence=PALETTE, text="conversion_rate_pct")
fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False, xaxis_title=None, yaxis_title="Conversion Rate (%)")
st.plotly_chart(fig, width="stretch")

with st.expander("📋 Lihat tabel conversion rate lengkap"):
    st.dataframe(conv_df, width="stretch", hide_index=True)
