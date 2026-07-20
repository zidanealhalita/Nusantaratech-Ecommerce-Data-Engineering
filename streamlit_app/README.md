# 🖥️ Streamlit Interactive Dashboard — NusantaraTech E-Commerce Data Mart

Versi **dashboard interaktif** dari data mart ini, dibangun dengan **Streamlit + Plotly**.
Berbeda dengan `reports/output/executive_dashboard.html` (dashboard statis, sekali generate),
dashboard Streamlit ini **membaca langsung dari `db/datamart.db`** setiap kali dijalankan dan
menyediakan **filter interaktif** (rentang tanggal, kategori, kota, device, dsb.) di setiap
halaman.

---

## ▶️ Cara Menjalankan

Pastikan pipeline ETL sudah pernah dijalankan minimal sekali (lihat README utama di root project)
sehingga `db/datamart.db` sudah tersedia:

```bash
# dari root folder project
pip install -r requirements.txt
python -m etl.run_etl

# jalankan dashboard
streamlit run streamlit_app/Home.py
```

Dashboard akan otomatis terbuka di browser pada `http://localhost:8501`.

> 💡 Jika ETL dijalankan ulang setelah dashboard sudah terbuka, klik tombol **🔄 Refresh Data**
> di sidebar untuk membersihkan cache dan memuat data terbaru tanpa perlu restart aplikasi.

---

## 🗂️ Struktur Halaman

Aplikasi ini adalah **Streamlit multipage app** dengan 1 halaman utama + 5 halaman analisis,
mengikuti konvensi folder `pages/` milik Streamlit:

```
streamlit_app/
├── Home.py                                 # Overview: ringkasan seluruh data mart
├── pages/
│   ├── 1_📈_Sales_Performance.py           # Revenue, profit, top produk, status order
│   ├── 2_👥_Customer_Analytics.py          # Segmentasi tier, top pelanggan, retensi
│   ├── 3_🌐_Web_Analytics.py               # Funnel konversi, device, response time
│   ├── 4_📦_Inventory_Warehouse.py         # Stok, mutasi gudang, produk cacat
│   └── 5_🧭_Executive_Summary.py           # Ringkasan lintas domain untuk manajemen
├── utils/
│   └── db.py                               # Koneksi DB, cached query, formatting, tema UI
├── assets/                                 # Screenshot dashboard (dokumentasi)
└── .streamlit/
    └── config.toml                         # Tema warna (selaras brand project)
```

| Halaman | Fokus Analisis | Filter Interaktif |
|---|---|---|
| **🏠 Home** | Ringkasan KPI seluruh data mart, jumlah baris tiap sumber data | — |
| **📈 Sales Performance** | Revenue/profit harian, revenue per kategori & kota, status order, metode pembayaran, top 10 produk | Rentang tanggal, kategori, kota, metode pembayaran, status order |
| **👥 Customer Analytics** | Segmentasi account tier, tren signup, top pelanggan, pelanggan dormant | Account tier, kota |
| **🌐 Web Analytics** | Funnel konversi, distribusi device, response time per halaman, conversion rate per kota | Platform (Desktop/Mobile) |
| **📦 Inventory & Warehouse** | Estimasi stok terendah, volume mutasi per gudang, produk paling sering rusak | Gudang, kategori produk |
| **🧭 Executive Summary** | Ringkasan harian lintas domain (sales × web × gudang), insight bisnis otomatis | — |

Setiap halaman memiliki:
- **KPI cards** di bagian atas.
- **Chart interaktif Plotly** (hover untuk detail, zoom, pan).
- **Tabel detail + tombol download CSV** (pada halaman yang relevan) di bagian bawah, dibungkus
  `st.expander` agar halaman tetap ringkas.

---

## 🖼️ Cuplikan Tampilan

| Home | Sales Performance |
|---|---|
| ![Home](assets/screenshot_home.png) | ![Sales](assets/screenshot_sales.png) |

| Web Analytics | Executive Summary |
|---|---|
| ![Web](assets/screenshot_web.png) | ![Executive](assets/screenshot_executive.png) |

---

## 🧠 Keputusan Teknis

- **Caching** — `utils/db.py` menggunakan `@st.cache_resource` untuk koneksi database (dibuka
  sekali per sesi) dan `@st.cache_data` untuk hasil query (dihitung ulang hanya saat filter
  berubah atau cache dibersihkan manual). Ini menjaga dashboard tetap responsif meski query SQL
  dijalankan berkali-kali saat user mengubah filter.
- **Read-only connection** — koneksi SQLite dibuka dengan mode `?mode=ro` agar dashboard tidak
  bisa secara tidak sengaja menulis/merusak data mart.
- **Query dinamis dengan filter** — setiap halaman membangun klausa `WHERE ... IN (...)` secara
  dinamis berdasarkan pilihan filter di sidebar, dieksekusi langsung sebagai SQL ke SQLite
  (bukan filter di sisi pandas), mendemonstrasikan pola *filter pushdown* ke database.
- **Konsistensi visual** — palet warna & helper format angka (`fmt_rupiah`, `fmt_number`,
  `fmt_pct`) disatukan di `utils/db.py` agar seluruh halaman (dan dashboard HTML statis di
  `reports/`) memiliki identitas visual yang konsisten.
- **Graceful error handling** — jika `db/datamart.db` belum ada (ETL belum dijalankan), setiap
  halaman menampilkan instruksi yang jelas alih-alih traceback error mentah
  (`utils.db.no_database_warning()`).

---

## 🌐 Opsi Deployment

Karena database bersifat **file SQLite tunggal** dan tidak memerlukan server database terpisah,
dashboard ini dapat di-deploy dengan mudah ke:

- **[Streamlit Community Cloud](https://streamlit.io/cloud)** — hubungkan repo GitHub ini,
  set entry point ke `streamlit_app/Home.py`, pastikan `db/datamart.db` ikut ter-commit
  (atau jalankan `python -m etl.run_etl` sebagai build step).
- **Docker** — bundling `db/datamart.db` + `streamlit_app/` + `requirements.txt` ke dalam image.
- **Server internal perusahaan** — jalankan via `streamlit run streamlit_app/Home.py
  --server.port 8501 --server.address 0.0.0.0` di belakang reverse proxy (Nginx/Caddy).

---

**Author:** Muhammad Zidane Alhalita
