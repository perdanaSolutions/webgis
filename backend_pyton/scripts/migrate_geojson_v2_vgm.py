"""
migrate_geojson_v2_vgm.py
-------------------------
Script migrasi GeoJSON → PostgreSQL (PostGIS) Relasional.
Mengikuti hirarki: Companies -> Areas -> Estates -> Afdelings -> Bloks -> Census Data.

Cara pakai dari root project:
    python scripts/migrate_geojson_v2_vgm.py --file data/TPA_SGA_2026.geojson
"""

import argparse
import time
import sys
import json
import math
from pathlib import Path

import geopandas as gpd
import psycopg2
from sqlalchemy import create_engine, text

# ============================================================
#  DEFAULT CONFIG — sesuaikan dengan database kamu
# ============================================================
DEFAULT_CONFIG = {
    "host"    : "localhost",
    "port"    : 5432,
    "database": "gm_gis_perkebunan",       # ← nama database PostgreSQL
    "username": "postgres",     # ← username PostgreSQL
    "password": "password",     # ← password PostgreSQL
}

DEFAULT_SCHEMA   = "public"
DEFAULT_IF_EXISTS = "replace"   # replace = kosongkan data lama & isi baru | append = tambah data
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
    import shapely
    from shapely.validation import make_valid
    from shapely.geometry import MultiPolygon, GeometryCollection

    if geom_dict is None:
        return None
    try:
        g = shapely.from_geojson(json.dumps(geom_dict))
        if g is None or g.is_empty:
            return None

        if not g.is_valid:
            g = make_valid(g)

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

        if g.geom_type == "Polygon":
            g = MultiPolygon([g])

        return g if not g.is_empty else None
    except Exception:
        return None


def load_geojson(filepath: str) -> gpd.GeoDataFrame:
    path = Path(filepath)
    if not path.exists():
        print(f"  ❌ File tidak ditemukan: {filepath}")
        sys.exit(1)

    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  📂 File  : {path.name} ({size_mb:.1f} MB)")

    try:
        gdf = gpd.read_file(filepath)
        print(f"  📊 Baris : {len(gdf):,}")
        print(f"  📐 Kolom : {len(gdf.columns)}")
        print(f"  🗺️  CRS   : {gdf.crs}")
        return gdf
    except Exception as e:
        print(f"  ⚠️  gpd.read_file gagal ({type(e).__name__})")
        print("  🔄 Fallback: manual JSON parsing...")

    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    features = raw.get("features", [])
    total = len(features)
    rows = []
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

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf


def clean_geodataframe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("\n🔧 Cleaning data...")
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    invalid = (~gdf.is_valid).sum()
    if invalid:
        gdf["geometry"] = gdf["geometry"].buffer(0)

    null_geom = gdf.geometry.isna().sum()
    if null_geom:
        gdf = gdf.dropna(subset=["geometry"])

    gdf.columns = [
        col.lower().replace(" ", "_").replace("-", "_")
        if col != "geometry" else col
        for col in gdf.columns
    ]

    dup_cols = [c for c in gdf.columns if c.endswith("_1")]
    if dup_cols:
        gdf = gdf.drop(columns=dup_cols)

    return gdf


def migrate(gdf: gpd.GeoDataFrame, engine, schema: str, if_exists: str):
    print(f"\n🚀 Memulai Migrasi Relasional ke Schema: '{schema}'")
    
    url = engine.url
    pg_conn = psycopg2.connect(
        host     = url.host,
        port     = url.port or 5432,
        dbname   = url.database,
        user     = url.username,
        password = url.password,
    )
    cur = pg_conn.cursor()

    if if_exists == "replace":
        print("  ⚠️ Mode 'replace' aktif: Mengosongkan data lama...")
        cur.execute(f"""
            TRUNCATE TABLE {schema}.block_census_data, {schema}.bloks, 
                           {schema}.afdelings, {schema}.estates, 
                           {schema}.areas, {schema}.companies 
            RESTART IDENTITY CASCADE;
        """)
        pg_conn.commit()

    total = len(gdf)
    written = 0

    def clean_val(v, default=None):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return default
        return v

    try:
        for _, row in gdf.iterrows():
            # Mengambil properti GeoJSON (Otomatis Lowercase karena fungsi cleaning)
            # kode_pt   = clean_val(row.get("kode_pt"), "TBP")
            # nama_pt   = clean_val(row.get("nama_pt"), "PT. TANJUNG BUYU PERKASA")
            # nama_area = clean_val(row.get("nama_area"), "BERAU")
            # kode_est  = clean_val(row.get("kode_est"), "TS1")
            # nama_est  = clean_val(row.get("nama_estate"), "Talisayan 1 Estate")
            # kode_afd  = clean_val(row.get("kode_afd"), "AFDI01")
            # kode_blok = clean_val(row.get("kode_blok"))

            kode_pt   = clean_val(row.get("kodept"), "TBP")
            nama_pt   = clean_val(row.get("pt"), "PT. TANJUNG BUYU PERKASA")
            nama_area = clean_val(row.get("area"), "BERAU")
            kode_est  = clean_val(row.get("kodeest"), "TS1")
            nama_est  = clean_val(row.get("estate"), "Talisayan 1 Estate")
            kode_afd  = clean_val(row.get("kodeafd"), "AFDI01")
            kode_blok = clean_val(row.get("kode_blok"))

            if not kode_blok:
                continue

            # 1. UPSERT COMPANIES
            cur.execute(f"""
                INSERT INTO {schema}.companies (kode_pt, nama_pt) VALUES (%s, %s)
                ON CONFLICT (kode_pt) DO UPDATE SET nama_pt = EXCLUDED.nama_pt RETURNING id;
            """, (kode_pt, nama_pt))
            company_id = cur.fetchone()[0]

            # 2. UPSERT AREAS
            cur.execute(f"SELECT id FROM {schema}.areas WHERE company_id = %s AND nama_area = %s;", (company_id, nama_area))
            area_res = cur.fetchone()
            if area_res:
                area_id = area_res[0]
            else:
                cur.execute(f"INSERT INTO {schema}.areas (company_id, nama_area) VALUES (%s, %s) RETURNING id;", (company_id, nama_area))
                area_id = cur.fetchone()[0]

            # 3. UPSERT ESTATES
            cur.execute(f"""
                INSERT INTO {schema}.estates (area_id, kode_est, nama_estate) VALUES (%s, %s, %s)
                ON CONFLICT (kode_est) DO UPDATE SET nama_estate = EXCLUDED.nama_estate, area_id = EXCLUDED.area_id RETURNING id;
            """, (area_id, kode_est, nama_est))
            estate_id = cur.fetchone()[0]

            # 4. UPSERT AFDELINGS
            cur.execute(f"SELECT id FROM {schema}.afdelings WHERE estate_id = %s AND kode_afd = %s;", (estate_id, kode_afd))
            afd_res = cur.fetchone()
            if afd_res:
                afdeling_id = afd_res[0]
            else:
                cur.execute(f"INSERT INTO {schema}.afdelings (estate_id, kode_afd) VALUES (%s, %s) RETURNING id;", (estate_id, kode_afd))
                afdeling_id = cur.fetchone()[0]

            # ========================================================
            # 5. UPSERT BLOKS
            # ========================================================
            geom_json = json.dumps(row["geometry"].__geo_interface__)
            cur.execute(f"""
                INSERT INTO {schema}.bloks (
                    afdeling_id, kode_blok, nama_blok, ownership, tahun_tanam, 
                    bulan_tanam, topografi, jenis_tanah, jenis_bibit, status_tanaman, 
                    luas_tanah, luas_tanam, geom
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromGeoJSON(%s))
                ON CONFLICT (kode_blok) DO UPDATE SET
                    afdeling_id = EXCLUDED.afdeling_id, 
                    nama_blok = EXCLUDED.nama_blok,
                    ownership = EXCLUDED.ownership, 
                    tahun_tanam = EXCLUDED.tahun_tanam, 
                    bulan_tanam = EXCLUDED.bulan_tanam,
                    topografi = EXCLUDED.topografi,
                    jenis_tanah = EXCLUDED.jenis_tanah,
                    jenis_bibit = EXCLUDED.jenis_bibit,
                    status_tanaman = EXCLUDED.status_tanaman,
                    luas_tanah = EXCLUDED.luas_tanah,
                    luas_tanam = EXCLUDED.luas_tanam,
                    geom = EXCLUDED.geom
                RETURNING id;
            """, (
                afdeling_id, 
                kode_blok, 
                clean_val(row.get("blok"), kode_blok),        # Mengambil "Blok" -> "blok"
                clean_val(row.get("ownership"), "Inti"), 
                int(clean_val(row.get("tt"), 2026)),           # Mengambil "TT" -> "tt"
                clean_val(row.get("blntanam")),                # Mengambil "BlnTanam" -> "blntanam"
                clean_val(row.get("topografi")), 
                clean_val(row.get("jenistanah")),              # Mengambil "JenisTanah" -> "jenistanah"
                clean_val(row.get("jenisbibit")),              # Mengambil "JenisBibit" -> "jenisbibit"
                clean_val(row.get("status"), "TM"),            # Mengambil "Status" -> "status"
                clean_val(row.get("ltanah")),                  # Mengambil "LTanah" -> "ltanah"
                clean_val(row.get("ltanam")),                  # Mengambil "LTanam" -> "ltanam"
                geom_json
            ))
            blok_id = cur.fetchone()[0]

            # ========================================================
            # 6. INSERT BLOCK CENSUS DATA (Menggunakan DO NOTHING)
            # ========================================================
            cur.execute(f"""
                INSERT INTO {schema}.block_census_data (
                    blok_id, tahun_sensus, pokok_target, pokok_aktual, titik_kosong,
                    pohon_sehat, pohon_semak, pohon_kuning, pohon_mati,
                    panjang_parit_meter, jumlah_jembatan, panjang_jalan_bantu_meter
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (
                blok_id, 
                2026, 
                clean_val(row.get("pokok"), 0),          
                clean_val(row.get("totpkk"), 0),         
                clean_val(row.get("ttkkosong"), 0),      
                clean_val(row.get("pkknormal"), 0),      
                clean_val(row.get("pkksemak"), 0),       
                clean_val(row.get("pkkkuning"), 0),      
                clean_val(row.get("pkkmati"), 0),        
                clean_val(row.get("drnmd"), 0.0),        
                clean_val(row.get("jembatan"), 0),       
                clean_val(row.get("jlnbantu"), 0.0)      
            ))

            written += 1
            if written % 20 == 0 or written == total:
                print(f"   [{written / total * 100:5.1f}%] Memproses {written:,}/{total:,} data blok", end="\r", flush=True)

        pg_conn.commit()
        print(f"\n  ✅ Berhasil memproses total {written:,} blok.")
    except Exception as e:
        pg_conn.rollback()
        print(f"\n  ❌ Terjadi kesalahan: {e}")
        raise e
    finally:
        cur.close()
        pg_conn.close()


def post_migrate(engine, schema: str):
    print("\n📐 Post-migration: Verifikasi & Indexing...")
    with engine.connect() as conn:
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_bloks_geom ON {schema}.bloks USING GIST (geom);'))
        total_pt = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.companies")).scalar()
        total_estate = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.estates")).scalar()
        total_blok = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.bloks")).scalar()
        conn.commit()

    print(f"  ✅ Spatial index 'idx_bloks_geom' siap.")
    print(f"  📊 Ringkasan: {total_pt:,} PT, {total_estate:,} Estate, {total_blok:,} Blok berhasil dimigrasi.")


def main():
    parser = argparse.ArgumentParser(description="Migrasi GeoJSON → PostGIS Relasional")
    parser.add_argument("--file",      default=None)
    parser.add_argument("--schema",    default=DEFAULT_SCHEMA)
    parser.add_argument("--if-exists", default=DEFAULT_IF_EXISTS)
    args = parser.parse_args()

    if args.file is None:
        args.file = input("📂 Path ke file GeoJSON: ").strip()

    print("\n" + "=" * 55 + "\n  MIGRASI GeoJSON RELASIONAL SAWIT\n" + "=" * 55)

    engine = build_engine(DEFAULT_CONFIG)
    if not test_connection(engine):
        sys.exit(1)

    gdf = load_geojson(args.file)
    gdf = clean_geodataframe(gdf)

    confirm = input(f"\n⚠️ Tulis {len(gdf):,} baris ke schema '{args.schema}' (mode: {args.if_exists})? [y/N]: ").strip().lower()
    if confirm == "y":
        migrate(gdf, engine, args.schema, args.if_exists)
        post_migrate(engine, args.schema)
        print("\n🎉 Selesai!")


if __name__ == "__main__":
    main()