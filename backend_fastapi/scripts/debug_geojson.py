"""
debug_geojson.py
----------------
Script untuk inspeksi struktur GeoJSON sebelum migrasi.
Jalankan: python scripts/debug_geojson.py --file path/ke/file.geojson
"""

import json
import sys
import argparse
from pathlib import Path


def inspect_coordinate(coord, depth=0, path=""):
    """Rekursif inspeksi tipe data koordinat."""
    indent = "  " * depth
    t = type(coord).__name__

    if isinstance(coord, (int, float)):
        print(f"{indent}[{path}] {t} = {coord}")
    elif isinstance(coord, list):
        print(f"{indent}[{path}] list[{len(coord)}]")
        if len(coord) > 0:
            # Tampilkan max 3 elemen
            for i, item in enumerate(coord[:3]):
                inspect_coordinate(item, depth + 1, f"{path}[{i}]")
            if len(coord) > 3:
                print(f"{indent}  ... ({len(coord) - 3} lagi)")
    elif isinstance(coord, tuple):
        print(f"{indent}[{path}] tuple{coord}")
    else:
        print(f"{indent}[{path}] ⚠️  TIPE TAK DIKENAL: {t} = {repr(coord)[:80]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=False, default=None)
    parser.add_argument("--feature", type=int, default=0, help="Index feature yang dicek (default: 0)")
    parser.add_argument("--count", type=int, default=5, help="Berapa feature yang dicek (default: 5)")
    args = parser.parse_args()

    if args.file is None:
        args.file = input("📂 Path ke file GeoJSON: ").strip()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File tidak ditemukan: {args.file}")
        sys.exit(1)

    print(f"\n📂 Membaca {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")

    with open(args.file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    features = raw.get("features", [])
    print(f"✅ Total features: {len(features):,}")
    print(f"📋 CRS: {raw.get('crs', 'tidak ada')}")
    print()

    # ── Cek N feature pertama ──────────────────────────────
    n = min(args.count, len(features))
    error_types = {}

    for idx in range(n):
        feat = features[idx]
        geom = feat.get("geometry")

        print("=" * 60)
        print(f"FEATURE #{idx}")
        print("=" * 60)

        if geom is None:
            print("  ⚠️  geometry = NULL")
            continue

        geom_type = geom.get("type", "UNKNOWN")
        coords    = geom.get("coordinates", [])
        print(f"  Type       : {geom_type}")

        # Hitung kedalaman koordinat
        def depth_and_types(obj, d=0):
            if isinstance(obj, list) and len(obj) > 0:
                return depth_and_types(obj[0], d + 1)
            return d, type(obj).__name__

        depth, leaf_type = depth_and_types(coords)
        print(f"  Coord depth: {depth} level")
        print(f"  Leaf type  : {leaf_type}")

        # Tampilkan koordinat pertama secara detail
        print(f"\n  📐 Struktur koordinat (3 level pertama):")
        inspect_coordinate(coords, depth=2, path="coords")

        # Test shapely
        print(f"\n  🧪 Test shapely.shape():")
        try:
            from shapely.geometry import shape
            g = shape(geom)
            print(f"     ✅ OK — {g.geom_type}, valid={g.is_valid}, empty={g.is_empty}")
        except Exception as e:
            err_key = type(e).__name__
            error_types[err_key] = error_types.get(err_key, 0) + 1
            print(f"     ❌ {type(e).__name__}: {e}")

            # Coba paksa float
            print(f"\n  🔧 Coba paksa koordinat ke float:")
            try:
                def force_float(obj):
                    if isinstance(obj, list):
                        return [force_float(x) for x in obj]
                    return float(obj)

                forced = {"type": geom_type, "coordinates": force_float(coords)}
                g2 = shape(forced)
                print(f"     ✅ Berhasil setelah paksa float — {g2.geom_type}")
            except Exception as e2:
                print(f"     ❌ Tetap gagal: {type(e2).__name__}: {e2}")

                # Inspeksi lebih dalam — cari elemen bermasalah
                print(f"\n  🔍 Cari elemen non-numeric:")
                def find_bad(obj, path=""):
                    if isinstance(obj, list):
                        for i, x in enumerate(obj):
                            find_bad(x, f"{path}[{i}]")
                    elif not isinstance(obj, (int, float)):
                        print(f"     ⚠️  {path} = {type(obj).__name__}: {repr(obj)[:60]}")

                find_bad(coords)

        print()

    # ── Scan semua features untuk error summary ────────────
    if len(features) > n:
        print("=" * 60)
        print(f"📊 SCAN SEMUA {len(features):,} FEATURES")
        print("=" * 60)

        from shapely.geometry import shape
        ok = 0
        errors = {}
        null_geom = 0
        geom_types_found = set()

        for i, feat in enumerate(features):
            if i % 500 == 0:
                print(f"  Scanning {i:,}/{len(features):,}...", end="\r")

            geom = feat.get("geometry")
            if geom is None:
                null_geom += 1
                continue

            geom_types_found.add(geom.get("type", "?"))

            try:
                g = shape(geom)
                ok += 1
            except Exception as e:
                key = f"{type(e).__name__}: {str(e)[:60]}"
                errors[key] = errors.get(key, 0) + 1

        print(f"\n  ✅ OK       : {ok:,}")
        print(f"  ❌ Error    : {sum(errors.values()):,}")
        print(f"  ⚠️  Null geom: {null_geom:,}")
        print(f"  🗺️  Geom types: {geom_types_found}")

        if errors:
            print(f"\n  Error breakdown:")
            for k, v in sorted(errors.items(), key=lambda x: -x[1]):
                print(f"    [{v:,}x] {k}")

        # Temukan contoh feature yang error
        if errors:
            print(f"\n  🔍 Contoh feature pertama yang error:")
            for i, feat in enumerate(features):
                geom = feat.get("geometry")
                if geom is None:
                    continue
                try:
                    shape(geom)
                except Exception as e:
                    print(f"  Feature #{i}:")
                    coords = geom.get("coordinates", [])

                    def find_bad_deep(obj, path="coords", max_show=5):
                        count = [0]
                        def _walk(o, p):
                            if count[0] >= max_show:
                                return
                            if isinstance(o, list):
                                for idx2, x in enumerate(o):
                                    _walk(x, f"{p}[{idx2}]")
                            elif not isinstance(o, (int, float)):
                                print(f"    ⚠️  {p} = {type(o).__name__}: {repr(o)[:60]}")
                                count[0] += 1
                        _walk(obj, path)

                    find_bad_deep(coords)
                    break


if __name__ == "__main__":
    main()