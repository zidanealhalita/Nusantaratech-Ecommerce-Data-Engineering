"""
generate_report.py
-------------------
Menghasilkan output REPORTING (bagian dari requirement 'MIS & Reporting')
berdasarkan data yang sudah ada di data mart (db/datamart.db):

1.  Satu set chart (.png) untuk KPI-KPI utama bisnis, disimpan di
    reports/output/charts/.
2.  Satu dashboard eksekutif (.html) yang merangkum seluruh KPI + chart
    dalam satu halaman, siap dibuka langsung di browser tanpa dependency
    tambahan (self-contained, chart di-embed sebagai base64).

Cara pakai:
    python -m reports.generate_report

Author : Muhammad Zidane Alhalita
"""

import base64
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from etl.config import DB_PATH

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CHART_DIR = OUTPUT_DIR / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# --- Palette warna konsisten untuk seluruh chart -----------------------------
NAVY = "#16233F"
GOLD = "#E8A33D"
TEAL = "#2E9C8F"
CORAL = "#E4634B"
SLATE = "#5A6B87"
BG = "#F7F6F2"
PALETTE = [NAVY, GOLD, TEAL, CORAL, SLATE, "#8E6C9E", "#C9A24B"]

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "axes.edgecolor": "#D8D5CC",
    "axes.labelcolor": NAVY,
    "text.color": NAVY,
    "xtick.color": NAVY,
    "ytick.color": NAVY,
    "font.family": "DejaVu Sans",
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "axes.grid": True,
    "grid.color": "#E4E1D8",
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def rupiah(x, _pos=None):
    if x >= 1e9:
        return f"Rp{x/1e9:.1f}M"
    if x >= 1e6:
        return f"Rp{x/1e6:.0f}jt"
    return f"Rp{x:,.0f}"


def fmt_axis_rupiah(ax, axis="y"):
    fmt = mticker.FuncFormatter(rupiah)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def savefig(fig, name):
    path = CHART_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor=BG)
    plt.close(fig)
    print(f"  -> chart tersimpan: {path.name}")
    return path


# =============================================================================
# CHART BUILDERS  (masing-masing return path file .png)
# =============================================================================

def chart_daily_revenue(conn):
    df = pd.read_sql("""
        SELECT d.full_date, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_date d ON fo.date_key = d.date_key
        GROUP BY d.full_date ORDER BY d.full_date
    """, conn)
    df["full_date"] = pd.to_datetime(df["full_date"])

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(df["full_date"], df["revenue"], color=NAVY, linewidth=2)
    ax.fill_between(df["full_date"], df["revenue"], color=GOLD, alpha=0.25)
    ax.set_title("Tren Revenue Harian - Juni 2026")
    ax.set_ylabel("Revenue")
    fmt_axis_rupiah(ax)
    fig.autofmt_xdate()
    return savefig(fig, "01_daily_revenue_trend.png")


def chart_revenue_by_category(conn):
    df = pd.read_sql("""
        SELECT dp.kategori, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_product dp ON fo.product_key = dp.product_key
        GROUP BY dp.kategori ORDER BY revenue DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(df["kategori"], df["revenue"], color=PALETTE[:len(df)])
    ax.invert_yaxis()
    ax.set_title("Revenue per Kategori Produk")
    fmt_axis_rupiah(ax, axis="x")
    for bar, val in zip(bars, df["revenue"]):
        ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
                rupiah(val), va="center", fontsize=9, color=NAVY)
    return savefig(fig, "02_revenue_by_category.png")


def chart_order_status(conn):
    df = pd.read_sql("SELECT status_order, COUNT(*) AS n FROM fact_orders GROUP BY status_order ORDER BY n DESC", conn)

    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, _texts, autotexts = ax.pie(
        df["n"], labels=None, autopct="%1.1f%%", startangle=90,
        colors=PALETTE[:len(df)], pctdistance=0.78,
        wedgeprops={"width": 0.42, "edgecolor": BG, "linewidth": 2},
    )
    plt.setp(autotexts, size=9, weight="bold", color="white")
    ax.set_title("Distribusi Status Order")
    ax.legend(wedges, df["status_order"], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    return savefig(fig, "03_order_status_distribution.png")


def chart_payment_method(conn):
    df = pd.read_sql("""
        SELECT dpm.payment_method_name, COUNT(*) AS n, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_payment_method dpm ON fo.payment_method_key = dpm.payment_method_key
        GROUP BY dpm.payment_method_name ORDER BY revenue DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(df["payment_method_name"], df["revenue"], color=PALETTE[:len(df)])
    ax.set_title("Revenue per Metode Pembayaran")
    fmt_axis_rupiah(ax)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    for bar, val in zip(bars, df["n"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{val} order",
                ha="center", va="bottom", fontsize=8, color=SLATE)
    return savefig(fig, "04_payment_method_revenue.png")


def chart_web_funnel(conn):
    df = pd.read_sql("""
        SELECT dpg.funnel_order, dpg.funnel_stage, COUNT(DISTINCT fwc.session_id) AS sessions
        FROM fact_web_clickstream fwc JOIN dim_page dpg ON fwc.page_key = dpg.page_key
        GROUP BY dpg.funnel_order, dpg.funnel_stage ORDER BY dpg.funnel_order
    """, conn)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(df["funnel_stage"], df["sessions"], color=TEAL)
    ax.invert_yaxis()
    ax.set_title("Funnel Konversi Web (Unique Session per Tahap)")
    for bar, val in zip(bars, df["sessions"]):
        ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height()/2, f"{val:,}",
                va="center", fontsize=9, color=NAVY)
    return savefig(fig, "05_web_conversion_funnel.png")


def chart_device_distribution(conn):
    df = pd.read_sql("""
        SELECT dd.device_type_code, COUNT(*) AS n
        FROM fact_web_clickstream fwc JOIN dim_device dd ON fwc.device_key = dd.device_key
        GROUP BY dd.device_type_code ORDER BY n DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, _texts, autotexts = ax.pie(
        df["n"], autopct="%1.1f%%", startangle=90, colors=PALETTE[:len(df)],
        pctdistance=0.78, wedgeprops={"width": 0.42, "edgecolor": BG, "linewidth": 2},
    )
    plt.setp(autotexts, size=9, weight="bold", color="white")
    ax.set_title("Distribusi Trafik per Tipe Perangkat")
    ax.legend(wedges, df["device_type_code"], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    return savefig(fig, "06_device_distribution.png")


def chart_top_products(conn):
    df = pd.read_sql("""
        SELECT dp.nama_produk, SUM(fo.gross_revenue_idr) AS revenue
        FROM fact_orders fo JOIN dim_product dp ON fo.product_key = dp.product_key
        WHERE fo.is_delivered = 1
        GROUP BY dp.nama_produk ORDER BY revenue DESC LIMIT 10
    """, conn)
    df = df.iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(df["nama_produk"], df["revenue"], color=GOLD)
    ax.set_title("Top 10 Produk Terlaris (Status: Delivered)")
    fmt_axis_rupiah(ax, axis="x")
    for bar, val in zip(bars, df["revenue"]):
        ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height()/2, rupiah(val),
                va="center", fontsize=8, color=NAVY)
    return savefig(fig, "07_top10_products.png")


def chart_warehouse_movement(conn):
    df = pd.read_sql("""
        SELECT dw.warehouse_name, fim.jenis_mutasi, SUM(fim.quantity_change) AS qty
        FROM fact_inventory_movements fim JOIN dim_warehouse dw ON fim.warehouse_key = dw.warehouse_key
        GROUP BY dw.warehouse_name, fim.jenis_mutasi
    """, conn)
    pivot = df.pivot(index="warehouse_name", columns="jenis_mutasi", values="qty").fillna(0)
    order = ["INBOUND", "RETUR_STOCK", "OUTBOUND", "ADJUSTMENT_DEFECT"]
    pivot = pivot[[c for c in order if c in pivot.columns]]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bottom = None
    colors = {"INBOUND": TEAL, "RETUR_STOCK": GOLD, "OUTBOUND": CORAL, "ADJUSTMENT_DEFECT": SLATE}
    for col in pivot.columns:
        ax.bar(pivot.index, pivot[col], bottom=bottom, label=col, color=colors.get(col))
        bottom = pivot[col] if bottom is None else bottom + pivot[col]
    ax.set_title("Volume Pergerakan Stok per Gudang per Jenis Mutasi")
    ax.legend(frameon=False, fontsize=8)
    return savefig(fig, "08_warehouse_movement.png")


# =============================================================================
# KPI SUMMARY (dipakai untuk kartu ringkasan di dashboard)
# =============================================================================

def compute_kpis(conn) -> dict:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "total_revenue": q("SELECT SUM(gross_revenue_idr) FROM fact_orders"),
        "total_profit": q("SELECT SUM(gross_profit_idr) FROM fact_orders"),
        "total_orders": q("SELECT COUNT(*) FROM fact_orders"),
        "total_customers": q("SELECT COUNT(*) FROM dim_customer"),
        "avg_order_value": q("SELECT AVG(gross_revenue_idr) FROM fact_orders"),
        "delivered_rate": q("""SELECT ROUND(SUM(is_delivered)*100.0/COUNT(*),1) FROM fact_orders"""),
        "cancelled_rate": q("""SELECT ROUND(SUM(is_cancelled)*100.0/COUNT(*),1) FROM fact_orders"""),
        "total_web_sessions": q("SELECT COUNT(DISTINCT session_id) FROM fact_web_clickstream"),
        "total_products": q("SELECT COUNT(*) FROM dim_product"),
        "net_stock_change": q("SELECT SUM(signed_quantity) FROM fact_inventory_movements"),
    }


# =============================================================================
# HTML DASHBOARD BUILDER
# =============================================================================

def img_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def build_html_dashboard(kpis: dict, chart_paths: dict) -> str:
    def card(label, value, sub=""):
        return f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>"""

    def fig(title, path, note=""):
        b64 = img_to_base64(path)
        return f"""
        <div class="chart-card">
            <img src="data:image/png;base64,{b64}" alt="{title}"/>
            {f'<p class="chart-note">{note}</p>' if note else ''}
        </div>"""

    kpi_cards = "".join([
        card("Total Revenue", rupiah(kpis["total_revenue"]), "Juni 2026"),
        card("Total Profit", rupiah(kpis["total_profit"]), f"Margin ~{kpis['total_profit']/kpis['total_revenue']*100:.1f}%"),
        card("Total Order", f"{kpis['total_orders']:,}", f"AOV {rupiah(kpis['avg_order_value'])}"),
        card("Delivered Rate", f"{kpis['delivered_rate']}%", f"Cancelled {kpis['cancelled_rate']}%"),
        card("Total Pelanggan", f"{kpis['total_customers']:,}", "Terdaftar di CRM"),
        card("Web Sessions", f"{kpis['total_web_sessions']:,}", "Unique session"),
        card("Total SKU Produk", f"{kpis['total_products']:,}", "Aktif di MDM"),
        card("Net Stock Movement", f"{kpis['net_stock_change']:+,}", "unit (INBOUND - OUTBOUND)"),
    ])

    charts_html = "".join([
        fig("Daily Revenue", chart_paths["daily_revenue"], "Fluktuasi revenue harian sepanjang Juni 2026."),
        fig("Revenue by Category", chart_paths["revenue_category"], "Kategori dengan kontribusi revenue tertinggi."),
        fig("Order Status", chart_paths["order_status"], "Proporsi status fulfilment seluruh order."),
        fig("Payment Method", chart_paths["payment_method"], "Preferensi metode pembayaran pelanggan."),
        fig("Web Funnel", chart_paths["web_funnel"], "Jumlah unique session pada tiap tahap funnel konversi."),
        fig("Device Distribution", chart_paths["device_dist"], "Segmentasi trafik berdasarkan perangkat."),
        fig("Top 10 Produk", chart_paths["top_products"], "Produk dengan revenue delivered tertinggi."),
        fig("Warehouse Movement", chart_paths["warehouse_move"], "Volume mutasi stok per gudang."),
    ])

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8"/>
<title>NusantaraTech E-Commerce | Executive Dashboard</title>
<style>
  :root {{
    --navy:#16233F; --gold:#E8A33D; --teal:#2E9C8F; --coral:#E4634B;
    --bg:#F7F6F2; --card:#FFFFFF; --border:#E7E4DA; --slate:#5A6B87;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--navy);
    font-family:'Segoe UI', Roboto, -apple-system, sans-serif;
  }}
  header {{
    background:var(--navy); color:#fff; padding:28px 40px;
    display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;
  }}
  header h1 {{ margin:0; font-size:22px; letter-spacing:0.3px; }}
  header p {{ margin:4px 0 0; color:#B9C2D6; font-size:13px; }}
  .badge {{
    background:var(--gold); color:var(--navy); font-weight:700; font-size:12px;
    padding:6px 14px; border-radius:20px;
  }}
  main {{ padding:32px 40px 60px; max-width:1280px; margin:0 auto; }}
  h2.section-title {{
    font-size:15px; text-transform:uppercase; letter-spacing:1px;
    color:var(--slate); border-bottom:2px solid var(--border); padding-bottom:8px; margin:36px 0 18px;
  }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; }}
  .kpi-card {{
    background:var(--card); border:1px solid var(--border); border-radius:10px;
    padding:18px 20px; border-top:4px solid var(--gold);
  }}
  .kpi-label {{ font-size:12px; color:var(--slate); text-transform:uppercase; letter-spacing:0.5px; }}
  .kpi-value {{ font-size:24px; font-weight:700; margin-top:6px; color:var(--navy); }}
  .kpi-sub {{ font-size:12px; color:var(--teal); margin-top:4px; font-weight:600; }}
  .chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .chart-card {{
    background:var(--card); border:1px solid var(--border); border-radius:10px;
    padding:14px; text-align:center;
  }}
  .chart-card img {{ width:100%; height:auto; border-radius:6px; }}
  .chart-note {{ font-size:12px; color:var(--slate); margin:8px 4px 2px; text-align:left; }}
  footer {{
    text-align:center; padding:24px; color:var(--slate); font-size:12px;
    border-top:1px solid var(--border); margin-top:40px;
  }}
  @media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns:repeat(2,1fr); }}
    .chart-grid {{ grid-template-columns:1fr; }}
    main {{ padding:24px 18px; }}
    header {{ padding:22px; }}
  }}
</style>
</head>
<body>
  <header>
    <div>
      <h1>NusantaraTech E-Commerce &mdash; Executive Dashboard</h1>
      <p>Data Mart Reporting | Periode: Juni 2026 | Sumber: CRM, MDM, OMS, WMS, Web Analytics</p>
    </div>
    <span class="badge">Auto-generated by ETL Pipeline</span>
  </header>
  <main>
    <h2 class="section-title">Ringkasan KPI Utama</h2>
    <div class="kpi-grid">{kpi_cards}</div>

    <h2 class="section-title">Visualisasi &amp; Analisis</h2>
    <div class="chart-grid">{charts_html}</div>
  </main>
  <footer>
    Dibuat oleh Muhammad Zidane Alhalita &middot; NusantaraTech E-Commerce Data Mart Project &middot;
    Generated from SQLite data mart (db/datamart.db)
  </footer>
</body>
</html>"""


def main():
    print("=== Generating reports & executive dashboard ===")
    conn = sqlite3.connect(DB_PATH)

    chart_paths = {
        "daily_revenue": chart_daily_revenue(conn),
        "revenue_category": chart_revenue_by_category(conn),
        "order_status": chart_order_status(conn),
        "payment_method": chart_payment_method(conn),
        "web_funnel": chart_web_funnel(conn),
        "device_dist": chart_device_distribution(conn),
        "top_products": chart_top_products(conn),
        "warehouse_move": chart_warehouse_movement(conn),
    }

    kpis = compute_kpis(conn)
    html = build_html_dashboard(kpis, chart_paths)

    dashboard_path = OUTPUT_DIR / "executive_dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    print(f"  -> dashboard tersimpan: {dashboard_path}")

    conn.close()
    print("=== Selesai ===")


if __name__ == "__main__":
    main()
