# 🗺️ GIS Project — FastAPI + PostGIS

## Struktur Project

```
gis_project/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── core/
│   │   ├── config.py            # Konfigurasi dari .env
│   │   └── database.py          # SQLAlchemy engine & session
│   ├── models/
│   │   └── blok.py              # ORM model tabel PostGIS
│   ├── routers/
│   │   └── blok.py              # Endpoint API spatial
│   └── schemas/
│       └── blok.py              # Pydantic response schemas
├── scripts/
│   └── migrate_geojson.py       # Script migrasi GeoJSON → PostGIS
├── .env.example
├── requirements.txt
└── README.md
```

---

## 1. Setup Awal

```bash
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

---

## 2. Siapkan Database PostgreSQL

```sql
-- Buka psql atau pgAdmin, buat database baru
CREATE DATABASE gis_db;

-- Aktifkan ekstensi PostGIS (jalankan di dalam database gis_db)
\c gis_db
CREATE EXTENSION IF NOT EXISTS postgis;
```

---

## 3. Konfigurasi .env

```bash
cp .env.example .env
# Edit .env sesuai konfigurasi PostgreSQL lokal kamu
```

---

## 4. Migrasi Data GeoJSON

```bash
# Cara 1 — Interaktif (akan minta path file)
python scripts/migrate_geojson.py

# Cara 2 — Dengan argumen langsung
python scripts/migrate_geojson.py --file data/TPA_SGA_2026.geojson --table tpa_sga_2026

# Cara 3 — Custom koneksi
python scripts/migrate_geojson.py \
  --file data/TPA_SGA_2026.geojson \
  --table tpa_sga_2026 \
  --host localhost \
  --port 5432 \
  --database gis_db \
  --username postgres \
  --password yourpassword
```

---

## 5. Jalankan FastAPI

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Buka di browser:
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc**      : http://localhost:8000/redoc

---

## 6. Endpoint yang Tersedia

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/blok` | List blok (tabular, bisa filter) |
| GET | `/api/v1/blok/{objectid}` | Detail satu blok |
| GET | `/api/v1/blok/geojson/all` | Semua blok sebagai GeoJSON |
| GET | `/api/v1/blok/geojson/bbox` | Blok dalam bounding box |
| GET | `/api/v1/blok/geojson/point` | Blok yang mengandung koordinat tertentu |
| GET | `/api/v1/blok/summary/estate` | Statistik agregat per estate |

### Contoh Request

```bash
# Semua blok di area BERAU
GET /api/v1/blok?area=BERAU

# GeoJSON blok dalam bounding box (lon/lat)
GET /api/v1/blok/geojson/bbox?min_lon=118.0&min_lat=1.0&max_lon=119.0&max_lat=2.0

# Blok yang mengandung titik koordinat tertentu (klik pada peta)
GET /api/v1/blok/geojson/point?lon=118.261&lat=1.507

# Statistik per estate, filter area BERAU
GET /api/v1/blok/summary/estate?area=BERAU
```
