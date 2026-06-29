# WebGIS Perdanait

Repository ini terdiri dari tiga komponen utama:

1. **API** (`API/`)  
   Express API untuk melayani data/filter GeoJSON.
2. **Backend Python** (`backend_pyton/`)  
   Backend GIS berbasis Python untuk kebutuhan API spasial dan integrasi PostGIS.
3. **GIS Dashboard** (`gis-dashboard/`)  
   Frontend berbasis Vue 3 + Nuxt untuk visualisasi peta dan dashboard.

---

## Struktur Project

```bash
webgis_perdanait/
├── API/
├── backend_pyton/
│   ├── app/
│   ├── scripts/
│   ├── data/
│   └── requirements.txt
├── gis-dashboard/
│   ├── pages/
│   ├── components/
│   ├── stores/
│   ├── plugins/
│   └── nuxt.config.ts
├── TODO.md
└── README.md
```

---

## Backend Python (GIS API)

> Sumber gabungan dari `backend_pyton/README.md` (diringkas dan dipertahankan inti setup).

### 1) Setup Awal

```bash
cd backend_pyton

# Buat virtual environment
python -m venv venv

# Aktifkan venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2) Siapkan PostgreSQL + PostGIS

```sql
CREATE DATABASE gis_db;
\c gis_db
CREATE EXTENSION IF NOT EXISTS postgis;
```

### 3) Konfigurasi Environment

```bash
cp .env.example .env
# lalu sesuaikan nilai koneksi database pada file .env
```

### 4) Migrasi Data GeoJSON

```bash
# Interaktif
python scripts/migrate_geojson.py

# Dengan argumen
python scripts/migrate_geojson.py --file data/TPA_SGA_2026.geojson --table tpa_sga_2026
```

### 5) Jalankan Service

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Akses dokumentasi:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 6) Endpoint Utama

- `GET /api/v1/blok`
- `GET /api/v1/blok/{objectid}`
- `GET /api/v1/blok/geojson/all`
- `GET /api/v1/blok/geojson/bbox`
- `GET /api/v1/blok/geojson/point`
- `GET /api/v1/blok/summary/estate`

---

## GIS Dashboard (Vue 3 + Nuxt)

> Sumber dari `gis-dashboard/README.md`, disesuaikan dari template menjadi panduan project ini.

### Menjalankan Dashboard

```bash
cd gis-dashboard
npm install
npm run dev
```

Aplikasi akan berjalan pada URL default Nuxt (umumnya `http://localhost:3000`).

### Build Production

```bash
npm run build
npm run preview
```

### Quality Checks

```bash
npm run lint
npm run test
```

---

## API (Express)

Untuk API Express di folder `API/`:

```bash
cd API
npm install
npm run dev
# atau npm start (tergantung script di package.json)
```

Pastikan endpoint API yang digunakan dashboard sesuai host/port yang dikonfigurasi.

---

## Catatan

- File markdown (`*.md`) secara umum di-ignore oleh `.gitignore` root.
- File `README.md` di root ini dikecualikan agar tetap ter-track di Git.
