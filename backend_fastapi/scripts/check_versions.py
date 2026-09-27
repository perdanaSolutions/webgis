"""
check_versions.py
-----------------
Cek versi library dan test berbagai cara parse MultiPolygon.
Jalankan: python scripts/check_versions.py
"""
import sys
import json

print("=" * 55)
print("  CEK VERSI LIBRARY")
print("=" * 55)

# Python
print(f"\n  Python     : {sys.version}")

# NumPy
try:
    import numpy as np
    print(f"  NumPy      : {np.__version__}")
except ImportError:
    print("  NumPy      : ❌ tidak terinstall")

# Shapely
try:
    import shapely
    print(f"  Shapely    : {shapely.__version__}")
    print(f"  GEOS       : {shapely.geos_version_string}")
except ImportError:
    print("  Shapely    : ❌ tidak terinstall")

# GeoPandas
try:
    import geopandas as gpd
    print(f"  GeoPandas  : {gpd.__version__}")
except ImportError:
    print("  GeoPandas  : ❌ tidak terinstall")

# Fiona
try:
    import fiona
    print(f"  Fiona      : {fiona.__version__}")
except ImportError:
    print("  Fiona      : ❌ tidak terinstall")

# PyProj
try:
    import pyproj
    print(f"  PyProj     : {pyproj.__version__}")
except ImportError:
    print("  PyProj     : ❌ tidak terinstall")

# ── Test berbagai metode parse ─────────────────────────────
print("\n" + "=" * 55)
print("  TEST METODE PARSE MULTIPOLYGON")
print("=" * 55)

# Koordinat sederhana untuk test
TEST_GEOM = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [118.261, 1.507],
                [118.262, 1.507],
                [118.262, 1.506],
                [118.261, 1.506],
                [118.261, 1.507],
            ]
        ]
    ]
}

# Test 1: shapely.geometry.shape
print("\n[1] shapely.geometry.shape():")
try:
    from shapely.geometry import shape
    g = shape(TEST_GEOM)
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

# Test 2: shapely.from_geojson
print("\n[2] shapely.from_geojson():")
try:
    import shapely
    g = shapely.from_geojson(json.dumps(TEST_GEOM))
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

# Test 3: shapely.geometry.MultiPolygon langsung
print("\n[3] shapely.geometry.MultiPolygon() langsung:")
try:
    from shapely.geometry import MultiPolygon, Polygon
    coords = TEST_GEOM["coordinates"]
    polys = []
    for poly in coords:
        exterior = [tuple(pt) for pt in poly[0]]
        holes    = [[tuple(pt) for pt in h] for h in poly[1:]]
        polys.append(Polygon(exterior, holes))
    g = MultiPolygon(polys)
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

# Test 4: numpy array approach
print("\n[4] Via numpy array:")
try:
    import numpy as np
    from shapely.geometry import MultiPolygon, Polygon
    coords = TEST_GEOM["coordinates"]
    polys = []
    for poly in coords:
        exterior = np.array(poly[0], dtype=np.float64)[:, :2]
        holes    = [np.array(h, dtype=np.float64)[:, :2] for h in poly[1:]]
        polys.append(Polygon(exterior, holes))
    g = MultiPolygon(polys)
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

# Test 5: WKT roundtrip
print("\n[5] Via WKT manual:")
try:
    import shapely.wkt
    coords = TEST_GEOM["coordinates"]
    rings_str = []
    for poly in coords:
        ring_parts = []
        for ring in poly:
            pts = ", ".join(f"{pt[0]} {pt[1]}" for pt in ring)
            ring_parts.append(f"({pts})")
        rings_str.append(f"({', '.join(ring_parts)})")
    wkt = f"MULTIPOLYGON ({', '.join(rings_str)})"
    g = shapely.wkt.loads(wkt)
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

# Test 6: shapely.from_wkb via pygeos path
print("\n[6] shapely.multipolygons() dengan array numpy:")
try:
    import shapely
    import numpy as np
    coords = TEST_GEOM["coordinates"]
    polys = []
    for poly in coords:
        exterior = np.array(poly[0], dtype=np.float64)[:, :2]
        p = shapely.polygons(exterior)
        polys.append(p)
    g = shapely.multipolygons(polys)
    print(f"    ✅ OK — {g.geom_type}")
except Exception as e:
    print(f"    ❌ {type(e).__name__}: {e}")

print("\n" + "=" * 55)
print("  REKOMENDASI")
print("=" * 55)
print("""
Setelah melihat hasil di atas, solusi yang paling mungkin:

  Jika [2] ✅ → gunakan shapely.from_geojson()  (paling mudah)
  Jika [3] ✅ → gunakan MultiPolygon() + tuple   (paling kompatibel)
  Jika [5] ✅ → gunakan WKT roundtrip            (paling safe)

  Jika semua ❌ → versi Shapely/NumPy tidak kompatibel,
  jalankan perintah berikut:
  
    pip install --upgrade shapely numpy
  atau:
    pip install shapely==2.0.6 numpy==1.26.4
""")