"""
pages/4_📦_Inventory_Warehouse.py
------------------------------------
Halaman analisis gudang & inventori: posisi stok bersih per produk/gudang,
ringkasan mutasi stok, dan produk dengan tingkat kerusakan tertinggi
(quality-control candidates).

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
    inject_base_css, page_header, fmt_number,
    NAVY, GOLD, TEAL, CORAL, SLATE, PALETTE, PLOTLY_LAYOUT,
)

st.set_page_config(page_title="Inventory & Warehouse | NusantaraTech", page_icon="📦", layout="wide")
inject_base_css()

if not db_is_ready():
    no_database_warning()

page_header("📦 Inventory & Warehouse Analytics", "Posisi stok, volume mutasi gudang, dan indikator kualitas produk.")

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
warehouses = get_distinct("dim_warehouse", "warehouse_name")
categories = get_distinct("dim_product", "kategori")

with st.sidebar:
    st.markdown("### 🔎 Filter")
    sel_warehouses = st.multiselect("Gudang", warehouses, default=warehouses)
    sel_categories = st.multiselect("Kategori produk", categories, default=categories)
    st.caption("Filter berlaku untuk seluruh chart & tabel di halaman ini.")

if not (sel_warehouses and sel_categories):
    st.warning("Pilih minimal 1 opsi pada setiap filter di sidebar untuk menampilkan data.")
    st.stop()


def in_clause(values):
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


WHERE = f"dw.warehouse_name IN {in_clause(sel_warehouses)} AND dp.kategori IN {in_clause(sel_categories)}"
JOIN = """
    FROM fact_inventory_movements fim
    JOIN dim_product dp ON fim.product_key = dp.product_key
    JOIN dim_warehouse dw ON fim.warehouse_key = dw.warehouse_key
"""

# =============================================================================
# KPI
# =============================================================================
kpi = run_query(f"""
    SELECT COUNT(*) AS total_movement,
           SUM(fim.signed_quantity) AS net_stock,
           SUM(CASE WHEN fim.jenis_mutasi='ADJUSTMENT_DEFECT' THEN fim.quantity_change ELSE 0 END) AS total_defect,
           SUM(CASE WHEN fim.jenis_mutasi='INBOUND' THEN fim.quantity_change ELSE 0 END) AS total_inbound,
           SUM(CASE WHEN fim.jenis_mutasi='OUTBOUND' THEN fim.quantity_change ELSE 0 END) AS total_outbound
    {JOIN} WHERE {WHERE}
""").iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔄 Total Transaksi Mutasi", fmt_number(kpi["total_movement"]))
c2.metric("📦 Net Stock Movement", f"{'+' if kpi['net_stock'] >= 0 else ''}{fmt_number(kpi['net_stock'])} unit")
c3.metric("⬇️ Total Inbound", f"{fmt_number(kpi['total_inbound'])} unit")
c4.metric("💥 Total Unit Rusak", f"{fmt_number(kpi['total_defect'])} unit")

st.divider()

# =============================================================================
# STOK TERENDAH (butuh restock) & MUTASI PER GUDANG
# =============================================================================
colA, colB = st.columns([1.1, 1])

with colA:
    st.markdown("#### 🚨 20 Kombinasi Produk-Gudang dengan Estimasi Stok Terendah")
    low_stock = run_query(f"""
        SELECT dp.product_id, dp.nama_produk, dw.warehouse_name,
               SUM(fim.signed_quantity) AS estimasi_stok_bersih
        {JOIN} WHERE {WHERE}
        GROUP BY dp.product_id, dp.nama_produk, dw.warehouse_name
        ORDER BY estimasi_stok_bersih ASC LIMIT 20
    """)
    fig = px.bar(
        low_stock, x="estimasi_stok_bersih", y="nama_produk", orientation="h",
        color="warehouse_name", color_discrete_sequence=PALETTE,
        hover_data=["product_id"],
    )
    fig.update_layout(**PLOTLY_LAYOUT, height=480, yaxis={"categoryorder": "total ascending"},
                       xaxis_title="Estimasi Stok Bersih (unit)", yaxis_title=None, legend_title="Gudang")
    st.plotly_chart(fig, width="stretch")
    st.caption("⚠️ Nilai negatif berarti volume OUTBOUND lebih besar dari INBOUND pada periode data ini "
               "(prioritas restock).")

with colB:
    st.markdown("#### Volume Mutasi per Gudang & Jenis")
    wh_df = run_query(f"""
        SELECT dw.warehouse_name, fim.jenis_mutasi, SUM(fim.quantity_change) AS qty
        {JOIN} WHERE {WHERE}
        GROUP BY dw.warehouse_name, fim.jenis_mutasi
    """)
    color_map = {"INBOUND": TEAL, "RETUR_STOCK": GOLD, "OUTBOUND": CORAL, "ADJUSTMENT_DEFECT": SLATE}
    fig = px.bar(wh_df, x="warehouse_name", y="qty", color="jenis_mutasi",
                 color_discrete_map=color_map, barmode="stack")
    fig.update_layout(**PLOTLY_LAYOUT, height=480, xaxis_title=None, yaxis_title="Unit", legend_title=None)
    st.plotly_chart(fig, width="stretch")

st.divider()

# =============================================================================
# PRODUK DENGAN TINGKAT KERUSAKAN TERTINGGI
# =============================================================================
st.markdown("#### 🔧 Top 10 Produk dengan Tingkat Kerusakan (ADJUSTMENT_DEFECT) Tertinggi")
defect_df = run_query(f"""
    SELECT dp.product_id, dp.nama_produk, dp.kategori,
           SUM(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN fim.quantity_change ELSE 0 END) AS total_unit_rusak,
           COUNT(CASE WHEN fim.jenis_mutasi = 'ADJUSTMENT_DEFECT' THEN 1 END) AS jumlah_kejadian
    {JOIN} WHERE {WHERE}
    GROUP BY dp.product_id, dp.nama_produk, dp.kategori
    HAVING total_unit_rusak > 0
    ORDER BY total_unit_rusak DESC LIMIT 10
""")
if defect_df.empty:
    st.caption("Tidak ada catatan kerusakan produk pada kombinasi filter ini.")
else:
    fig = px.bar(defect_df.iloc[::-1], x="total_unit_rusak", y="nama_produk", orientation="h",
                 color="kategori", color_discrete_sequence=PALETTE, text="jumlah_kejadian")
    fig.update_traces(texttemplate="%{text} kejadian", textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=400, xaxis_title="Total Unit Rusak", yaxis_title=None,
                       legend_title="Kategori")
    st.plotly_chart(fig, width="stretch")

with st.expander("📋 Lihat & unduh data mutasi stok (hasil filter saat ini)"):
    detail = run_query(f"""
        SELECT fim.movement_id, fim.movement_datetime, dp.product_id, dp.nama_produk, dw.warehouse_name,
               fim.jenis_mutasi, fim.quantity_change, fim.signed_quantity, fim.operator_id
        {JOIN} WHERE {WHERE}
        ORDER BY fim.movement_datetime DESC LIMIT 2000
    """)
    st.dataframe(detail, width="stretch", height=380)
    st.download_button(
        "⬇️ Download CSV", detail.to_csv(index=False).encode("utf-8"),
        file_name="inventory_movements_filtered.csv", mime="text/csv",
    )
