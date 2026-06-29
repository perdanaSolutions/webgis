"""
migrate_geojson.py
------------------
Script migrasi GeoJSON → PostgreSQL (PostGIS) lokal.

Cara pakai:
    python scripts/migrate_geojson.py --file data/TPA_SGA_2026.geojson --table tpa_sga_2026

Atau edit DEFAULT_CONFIG di bawah lalu jalankan langsung:
    python scripts/migrate_geojson.py
"""

import argparse
import time
import sys
from pathlib import Path

import geopandas as gpd
from sqlalchemy import create_engine, text

# ============================================================
#  DEFAULT CONFIG — edit sesuai kebutuhan
# ============================================================
DEFAULT_CONFIG = {
    "host"    : "localhost",
    "port"    : 5432,
    "database": "gis_db",       # ← nama database PostgreSQL kamu
    "username": "postgres",     # ← username PostgreSQL
    "password": "password",     # ← password PostgreSQL
}

DEFAULT_TABLE    = "tpa_sga_2026"
DEFAULT_SCHEMA   = "public"
DEFAULT_IF_EXISTS = "replace"   # replace | append | fail
CHUNK_SIZE       = 500
# ============================================================


def build_engine(config: dict):
    conn_str = (
        f"postgresql+psycopg2://{config['username']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    return create_engine(conn_str)


def test_connection(engine) -> bool:
    try:
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version();")).scalar()
            print(f"  ✅ PostgreSQL : {ver[:60]}...")

            # Aktifkan PostGIS jika belum
            try:
                pg_ver = conn.execute(text("SELECT PostGIS_Version();")).scalar()
                print(f"  ✅ PostGIS    : {pg_ver}")
            except Exception:
                print("  ⚠️  PostGIS belum aktif — mengaktifkan...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                print("  ✅ PostGIS berhasil diaktifkan")
        return True
    except Exception as e:
        print(f"  ❌ Koneksi gagal: {e}")
        return False


def _parse_geometry(geom_dict: dict):
    """
    Parse satu geometry dict menggunakan shapely.from_geojson().
    Kompatibel NumPy 2.x + Shapely 2.0.x.

    Setelah make_valid(), hasilnya bisa GeometryCollection —
    kita ekstrak semua Polygon/MultiPolygon lalu wrap ke MultiPolygon.
    """
    import json
    import shapely
    from shapely.validation import make_valid
    from shapely.geometry import MultiPolygon, GeometryCollection

    if geom_dict is None:
        return None
    try:
        g = shapely.from_geojson(json.dumps(geom_dict))
        if g is None or g.is_empty:
            return None

        # Pastikan valid
        if not g.is_valid:
            g = make_valid(g)

        # Jika make_valid menghasilkan GeometryCollection,
        # ekstrak semua komponen Polygon/MultiPolygon
        if isinstance(g, GeometryCollection) and not isinstance(g, MultiPolygon):
            polys = []
            for part in g.geoms:
                if part.geom_type == "Polygon":
                    polys.append(part)
                elif part.geom_type == "MultiPolygon":
                    polys.extend(part.geoms)
            if not polys:
                return None
            g = MultiPolygon(polys) if len(polys) > 1 else MultiPolygon([polys[0]])

        # Normalisasi Polygon tunggal → MultiPolygon
        if g.geom_type == "Polygon":
            g = MultiPolygon([g])

        return g if not g.is_empty else None

    except Exception:
        return None


def load_geojson(filepath: str) -> gpd.GeoDataFrame:
    """
    Baca GeoJSON ke GeoDataFrame.
    Strategi 1: gpd.read_file (Fiona) — cepat.
    Strategi 2: Manual JSON + shapely.from_geojson — kompatibel NumPy 2.x.
    """
    import json

    path = Path(filepath)
    if not path.exists():
        print(f"  ❌ File tidak ditemukan: {filepath}")
        sys.exit(1)

    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  📂 File  : {path.name} ({size_mb:.1f} MB)")

    # ── Strategi 1: gpd.read_file via Fiona ───────────────────
    try:
        gdf = gpd.read_file(filepath)
        print(f"  📊 Baris : {len(gdf):,}")
        print(f"  📐 Kolom : {len(gdf.columns)}")
        print(f"  🗺️  CRS   : {gdf.crs}")
        return gdf
    except Exception as e:
        print(f"  ⚠️  gpd.read_file gagal ({type(e).__name__})")
        print("  🔄 Fallback: manual JSON + shapely.from_geojson()...")

    # ── Strategi 2: manual parse ───────────────────────────────
    print("  📖 Membaca JSON ke memori...", end=" ", flush=True)
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)
    print("✅")

    features   = raw.get("features", [])
    total      = len(features)
    rows       = []
    skip_count = 0

    print(f"  🔄 Parsing {total:,} features...")

    for i, feat in enumerate(features):
        if i % 200 == 0:
            pct = i / total * 100
            print(f"     [{pct:5.1f}%] {i:,}/{total:,}", end="\r", flush=True)

        geom = _parse_geometry(feat.get("geometry"))
        if geom is None:
            skip_count += 1
            continue

        props = dict(feat.get("properties") or {})
        props["geometry"] = geom
        rows.append(props)

    print(f"\n  ✅ Berhasil parse : {len(rows):,} features")
    if skip_count:
        print(f"  ⚠️  Dilewati       : {skip_count:,} features (null/invalid)")

    if not rows:
        print("  ❌ Tidak ada feature yang berhasil di-parse!")
        sys.exit(1)

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    print(f"  📐 Kolom : {len(gdf.columns)}")
    print(f"  🗺️  CRS   : {gdf.crs}")
    return gdf


def clean_geodataframe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("\n🔧 Cleaning data...")

    # 1. Normalisasi CRS ke EPSG:4326
    if gdf.crs is None:
        print("  ⚠️  CRS tidak ada → set ke EPSG:4326")
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        print(f"  🔄 Konversi CRS {gdf.crs} → EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)
    else:
        print("  ✅ CRS sudah EPSG:4326")

    # 2. Perbaiki geometri tidak valid
    invalid = (~gdf.is_valid).sum()
    if invalid:
        print(f"  ⚠️  {invalid} geometri tidak valid → diperbaiki dengan buffer(0)")
        gdf["geometry"] = gdf["geometry"].buffer(0)
    else:
        print("  ✅ Semua geometri valid")

    # 3. Hapus baris dengan geometri null
    null_geom = gdf.geometry.isna().sum()
    if null_geom:
        print(f"  ⚠️  {null_geom} baris geometri null → dihapus")
        gdf = gdf.dropna(subset=["geometry"])

    # 4. Bersihkan nama kolom
    gdf.columns = [
        col.lower().replace(" ", "_").replace("-", "_")
        if col != "geometry" else col
        for col in gdf.columns
    ]

    # 5. Hapus kolom duplikat suffix '_1' dari GeoJSON export
    dup_cols = [c for c in gdf.columns if c.endswith("_1")]
    if dup_cols:
        print(f"  🗑️  Hapus kolom duplikat: {dup_cols}")
        gdf = gdf.drop(columns=dup_cols)

    print(f"  ✅ Selesai: {len(gdf):,} baris × {len(gdf.columns)} kolom")
    return gdf


def migrate(gdf: gpd.GeoDataFrame, engine, table: str, schema: str, if_exists: str):
    """
    Tulis GeoDataFrame ke PostGIS menggunakan psycopg2 langsung.
    Menghindari konflik GeoAlchemy2 dtype vs pandas/SQLAlchemy versi baru.
    """
    import json
    import psycopg2
    from psycopg2.extras import execute_values
    from sqlalchemy import text

    # Deteksi tipe geometri dominan
    geom_types = gdf.geom_type.unique()
    geom_type  = "MULTIPOLYGON" if len(geom_types) != 1 or geom_types[0] != "Polygon" else "POLYGON"

    print(f"\n🚀 Migrasi ke '{schema}.{table}'")
    print(f"   Tipe geometri : {geom_type}")
    print(f"   Mode          : {if_exists}")
    print(f"   Chunk size    : {CHUNK_SIZE}")

    # Ambil kolom non-geometry
    non_geom_cols = [c for c in gdf.columns if c != "geometry"]

    # ── Buat / bersihkan tabel dulu via SQLAlchemy ────────────
    with engine.begin() as conn:
        if if_exists == "replace":
            conn.execute(text(f'DROP TABLE IF EXISTS {schema}."{table}" CASCADE;'))

        # Bangun DDL kolom non-geometry dari dtype pandas
        def pandas_dtype_to_pg(col, dtype):
            s = str(dtype)
            if "int" in s:   return "BIGINT"
            if "float" in s: return "DOUBLE PRECISION"
            if "bool" in s:  return "BOOLEAN"
            return "TEXT"

        col_defs = ",\n  ".join(
            f'"{c}" {pandas_dtype_to_pg(c, gdf[c].dtype)}'
            for c in non_geom_cols
        )
        ddl = f"""
            CREATE TABLE IF NOT EXISTS {schema}."{table}" (
              {col_defs},
              geometry geometry(GEOMETRY, 4326)
            );
        """
        conn.execute(text(ddl))

    # ── Insert baris per chunk via psycopg2 execute_values ────
    url = engine.url
    pg_conn = psycopg2.connect(
        host     = url.host,
        port     = url.port or 5432,
        dbname   = url.database,
        user     = url.username,
        password = url.password,
    )
    cur = pg_conn.cursor()

    placeholders = ", ".join(["%s"] * len(non_geom_cols))
    col_names    = ", ".join(f'"{c}"' for c in non_geom_cols)
    insert_sql   = (
        f'INSERT INTO {schema}."{table}" ({col_names}, geometry) '
        f"VALUES ({placeholders}, ST_GeomFromGeoJSON(%s))"
    )

    total   = len(gdf)
    start   = time.time()
    written = 0

    for chunk_start in range(0, total, CHUNK_SIZE):
        chunk = gdf.iloc[chunk_start : chunk_start + CHUNK_SIZE]
        rows  = []
        for _, row in chunk.iterrows():
            vals = []
            for c in non_geom_cols:
                v = row[c]
                # Konversi NaN → None supaya psycopg2 tulis NULL
                try:
                    import math
                    if v is None or (isinstance(v, float) and math.isnan(v)):
                        v = None
                except Exception:
                    pass
                vals.append(v)
            # Geometry sebagai GeoJSON string
            geom_json = json.dumps(row["geometry"].__geo_interface__)
            vals.append(geom_json)
            rows.append(tuple(vals))

        cur.executemany(insert_sql, rows)
        pg_conn.commit()
        written += len(rows)
        pct = written / total * 100
        print(f"   [{pct:5.1f}%] {written:,}/{total:,} baris", end="\r", flush=True)

    cur.close()
    pg_conn.close()

    elapsed = time.time() - start
    print(f"\n  ✅ Selesai dalam {elapsed:.1f} detik ({total:,} baris)")


def post_migrate(engine, table: str, schema: str):
    print("\n📐 Post-migration: index & verifikasi...")
    with engine.connect() as conn:
        # Spatial index
        idx = f"idx_{table}_geometry"
        conn.execute(text(
            f'CREATE INDEX IF NOT EXISTS {idx} '
            f'ON {schema}."{table}" USING GIST (geometry);'
        ))

        # Verifikasi jumlah baris
        count = conn.execute(
            text(f'SELECT COUNT(*) FROM {schema}."{table}"')
        ).scalar()

        # Bounding box
        bbox = conn.execute(text(f"""
            SELECT
                ST_XMin(ST_Extent(geometry)) AS min_lon,
                ST_YMin(ST_Extent(geometry)) AS min_lat,
                ST_XMax(ST_Extent(geometry)) AS max_lon,
                ST_YMax(ST_Extent(geometry)) AS max_lat
            FROM {schema}."{table}"
        """)).fetchone()

        conn.commit()

    print(f"  ✅ Spatial index '{idx}' dibuat")
    print(f"  ✅ Total baris : {count:,}")
    print(f"  🗺️  Bounding box:")
    print(f"     Lon: {bbox[0]:.6f} → {bbox[2]:.6f}")
    print(f"     Lat: {bbox[1]:.6f} → {bbox[3]:.6f}")


def main():
    parser = argparse.ArgumentParser(description="Migrasi GeoJSON → PostGIS")
    parser.add_argument("--file",      default=None,              help="Path ke file GeoJSON")
    parser.add_argument("--table",     default=DEFAULT_TABLE,     help="Nama tabel tujuan")
    parser.add_argument("--schema",    default=DEFAULT_SCHEMA,    help="Schema PostgreSQL")
    parser.add_argument("--if-exists", default=DEFAULT_IF_EXISTS, help="replace|append|fail")
    parser.add_argument("--host",      default=DEFAULT_CONFIG["host"])
    parser.add_argument("--port",      default=DEFAULT_CONFIG["port"], type=int)
    parser.add_argument("--database",  default=DEFAULT_CONFIG["database"])
    parser.add_argument("--username",  default=DEFAULT_CONFIG["username"])
    parser.add_argument("--password",  default=DEFAULT_CONFIG["password"])
    args = parser.parse_args()

    if args.file is None:
        # Jika tidak ada argumen, minta input interaktif
        args.file = input("📂 Path ke file GeoJSON: ").strip()

    print("\n" + "=" * 55)
    print("  MIGRASI GeoJSON → PostgreSQL (PostGIS)")
    print("=" * 55)

    # Bangun config dari args
    config = {
        "host": args.host, "port": args.port,
        "database": args.database,
        "username": args.username, "password": args.password,
    }
    engine = build_engine(config)

    # 1. Test koneksi
    print("\n🔌 Koneksi ke database...")
    if not test_connection(engine):
        sys.exit(1)

    # 2. Load GeoJSON
    print("\n📂 Membaca GeoJSON...")
    gdf = load_geojson(args.file)

    # 3. Cleaning
    gdf = clean_geodataframe(gdf)

    # 4. Konfirmasi sebelum migrasi
    print(f"\n⚠️  Akan menulis {len(gdf):,} baris ke '{args.schema}.{args.table}' (mode: {args.if_exists})")
    confirm = input("   Lanjutkan? [y/N]: ").strip().lower()
    if confirm != "y":
        print("❌ Dibatalkan.")
        sys.exit(0)

    # 5. Migrasi
    migrate(gdf, engine, args.table, args.schema, args.if_exists)

    # 6. Post-migration
    post_migrate(engine, args.table, args.schema)

    print("\n🎉 Migrasi selesai! Tabel siap dipakai di FastAPI.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()