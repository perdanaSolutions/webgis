"""
Gabungkan blok kembar di master: kode blok sama dalam satu estate tetapi tercatat di beberapa afdeling.

GeoJSON batas blok (sumber resmi struktur) menentukan blok yang benar: dari setiap kelompok kembar,
blok yang estate+afdeling+bloknya ada di GeoJSON dipertahankan, sisanya ("blok lama") dilebur ke sana:
- areal statement, produksi, rotasi, dan semua data spasial dipindah ke blok yang benar;
- produksi di bulan yang sama digabung per kolom (nilai kosong/0 diisi dari blok lama). Bila ada kolom
  yang terisi di kedua blok, kelompok itu DILEWATI (tidak ada angka yang ditimpa);
- areal statement/rotasi/batas blok di bulan yang sama juga membuat kelompok itu dilewati;
- id blok lama dicatat di audit.legacy_id_maps sehingga id lama yang tersimpan di FE tetap mengarah ke
  blok yang benar, lalu blok lama dihapus.
Kelompok yang tidak ditunjuk GeoJSON (tidak ada atau lebih dari satu blok yang cocok) tidak diubah.

    python -m scripts.merge_duplicate_blocks <file.geojson>            # uji coba: laporan saja, tidak menyimpan
    python -m scripts.merge_duplicate_blocks <file.geojson> --apply    # simpan
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.data_version import GEOJSON, HISTORY, bump  # noqa: E402
from app.utils.geojson import parse_features  # noqa: E402
from app.utils.parsing import clean_str, norm_key  # noqa: E402

PRODUCTION_COLUMNS = ("ffb_actual_kg", "ffb_budget_kg", "ffb_census_kg", "bunches_actual", "bunches_budget",
                      "bunches_census", "bjr_actual", "bjr_budget", "bjr_census")
# Tabel dengan unik (block_id, period): bulan yang sama di kedua blok = bentrok (selain produksi).
PERIOD_UNIQUE_TABLES = ("trx.area_statements", "trx.harvest_rotations", "spatial.block_boundaries")
MOVE_TABLES = ("trx.area_statements", "trx.harvest_rotations", "spatial.block_boundaries", "spatial.bridges",
               "spatial.drainage_points", "spatial.geo_dyn_geo_cek_data", "spatial.landuse_polygons", "spatial.roads",
               "spatial.slope_polygons", "spatial.tph_points", "spatial.tree_censuses")


def geojson_paths(path: Path) -> set[tuple[str, str, str]]:
    paths = set()
    for feature in parse_features(path.read_bytes()):
        props = feature.get("properties") or {}
        estate = clean_str(props.get("Est_ID") or props.get("EstID") or props.get("Est") or props.get("Estate"))
        division, block = clean_str(props.get("Afdeling")), clean_str(props.get("Blok"))
        if estate and division and block:
            paths.add((norm_key(estate), norm_key(division), norm_key(block)))
    return paths


def plan_pairs(db, paths: set[tuple[str, str, str]]) -> tuple[list[dict], list[dict]]:
    """(pasangan blok lama -> blok benar, kelompok kembar yang tidak bisa ditentukan)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in db.execute(text("""
        SELECT bl.id, es.code AS estate, dv.code AS division, bl.code AS block
        FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
        JOIN master.estates es ON es.id = dv.estate_id
    """)).mappings():
        groups.setdefault((norm_key(r["estate"]), norm_key(r["block"])), []).append(dict(r))
    pairs, unresolved = [], []
    for (estate, block), rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        keepers = [r for r in rows if (estate, norm_key(r["division"]), block) in paths]
        if len(keepers) != 1:
            unresolved.append({"blok": f"{rows[0]['estate']}/{rows[0]['block']}",
                               "afdeling": sorted(r["division"] for r in rows), "ditunjuk_geojson": len(keepers)})
            continue
        for r in rows:
            if r["id"] != keepers[0]["id"]:
                pairs.append({"old": r["id"], "keep": keepers[0]["id"],
                              "label": f"{r['estate']}/{r['block']}: {r['division']} -> {keepers[0]['division']}"})
    return pairs, unresolved


def conflicting_pairs(db) -> set[int]:
    """Blok lama yang tidak aman dilebur: bulan sama di tabel unik, atau kolom produksi terisi di kedua blok."""
    bad = set()
    for table in PERIOD_UNIQUE_TABLES:
        bad |= set(db.execute(text(f"""
            SELECT p.old FROM _merge p JOIN {table} a ON a.block_id = p.old
            JOIN {table} b ON b.block_id = p.keep AND b.period = a.period
        """)).scalars())
    both_filled = " OR ".join(f"(COALESCE(a.{c}, 0) <> 0 AND COALESCE(b.{c}, 0) <> 0)" for c in PRODUCTION_COLUMNS)
    bad |= set(db.execute(text(f"""
        SELECT p.old FROM _merge p JOIN trx.block_productions a ON a.block_id = p.old
        JOIN trx.block_productions b ON b.block_id = p.keep AND b.period = a.period
        WHERE {both_filled}
    """)).scalars())
    return bad


def merge(db) -> dict:
    counts = {}
    fill = ", ".join(f"{c} = CASE WHEN COALESCE(b.{c}, 0) = 0 THEN a.{c} ELSE b.{c} END" for c in PRODUCTION_COLUMNS)
    counts["produksi_digabung_per_kolom"] = db.execute(text(f"""
        UPDATE trx.block_productions b SET {fill}
        FROM _merge p JOIN trx.block_productions a ON a.block_id = p.old
        WHERE b.block_id = p.keep AND b.period = a.period
    """)).rowcount
    db.execute(text("""
        DELETE FROM trx.block_productions a USING _merge p, trx.block_productions b
        WHERE a.block_id = p.old AND b.block_id = p.keep AND b.period = a.period
    """))
    counts["produksi_dipindah"] = db.execute(text(
        "UPDATE trx.block_productions t SET block_id = p.keep FROM _merge p WHERE t.block_id = p.old")).rowcount
    for table in MOVE_TABLES:
        moved = db.execute(text(f"UPDATE {table} t SET block_id = p.keep FROM _merge p WHERE t.block_id = p.old")).rowcount
        if moved:
            counts[f"{table}_dipindah"] = moved
    db.execute(text("""
        UPDATE audit.legacy_id_maps m SET new_id = p.keep::text FROM _merge p
        WHERE m.table_name = 'master.blocks' AND m.new_id = p.old::text
    """))
    db.execute(text("""
        INSERT INTO audit.legacy_id_maps (table_name, legacy_id, new_id)
        SELECT 'master.blocks', p.old::text, p.keep::text FROM _merge p
    """))
    counts["blok_lama_dihapus"] = db.execute(text(
        "DELETE FROM master.blocks bl USING _merge p WHERE bl.id = p.old")).rowcount
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("geojson", type=Path, help="GeoJSON batas blok (sumber resmi estate/afdeling/blok)")
    parser.add_argument("--apply", action="store_true", help="simpan perubahan (tanpa ini hanya uji coba)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        pairs, unresolved = plan_pairs(db, geojson_paths(args.geojson))
        db.execute(text("CREATE TEMP TABLE _merge (old bigint PRIMARY KEY, keep bigint NOT NULL) ON COMMIT DROP"))
        for pair in pairs:
            db.execute(text("INSERT INTO _merge VALUES (:old, :keep)"), pair)
        skipped = conflicting_pairs(db)
        if skipped:
            db.execute(text("DELETE FROM _merge WHERE old = ANY(:ids)"), {"ids": sorted(skipped)})
        counts = merge(db)
        print(f"Database      : {settings.DB_NAME}")
        print(f"Mode          : {'SIMPAN' if args.apply else 'UJI COBA (tidak disimpan)'}")
        print(f"Blok dilebur  : {len(pairs) - len(skipped)} (dari {len(pairs)} blok lama)")
        for key, value in counts.items():
            print(f"  {key}: {value}")
        if skipped:
            print(f"Dilewati karena bentrok ({len(skipped)}):")
            for pair in pairs:
                if pair["old"] in skipped:
                    print(f"  {pair['label']}")
        print(f"Kelompok kembar tanpa petunjuk GeoJSON ({len(unresolved)}), tidak diubah:")
        for item in unresolved:
            print(f"  {item['blok']} afdeling {', '.join(item['afdeling'])} (cocok di GeoJSON: {item['ditunjuk_geojson']})")
        if args.apply:
            bump(db, GEOJSON)
            bump(db, HISTORY)
            db.commit()
            print("Selesai: perubahan disimpan.")
        else:
            db.rollback()
            print("Uji coba selesai: tidak ada yang disimpan. Jalankan dengan --apply untuk menyimpan.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
