"""
Penjelasan rinci (bahasa Indonesia) kenapa geometri GeoJSON satu fitur tidak bisa dipakai.

Hanya dipanggil untuk fitur yang DITOLAK `prepare_geometry` (jalur gagal saja), jadi tidak
membebani fitur yang valid. Pesan memuat: apa masalahnya, di koordinat mana (bila ada),
tipe yang diharapkan layer, dan saran perbaikan singkat (umumnya di QGIS).
"""
import math
import re
from typing import Any

import shapely
from shapely.errors import ShapelyError
from shapely.geometry import shape
from shapely.validation import explain_validity, make_valid

GEOJSON_TYPES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
FIX_HINT = "Perbaiki di QGIS: Vector > Geometry Tools > Fix Geometries (atau Check Validity untuk melihat lokasinya)."

# Alasan GEOS (explain_validity) -> penjelasan + saran.
GEOS_REASONS = [
    ("Ring Self-intersection", "cincin (ring) poligon memotong/menyentuh dirinya sendiri (bentuk angka 8 / pita terpelintir)"),
    ("Self-intersection", "garis batas poligon saling berpotongan (self-intersection)"),
    ("Too few points", "komponen geometri punya terlalu sedikit titik unik (poligon minimal 3 titik berbeda + titik penutup)"),
    ("Hole lies outside shell", "lubang (hole/enclave) berada di luar cincin luar poligon"),
    ("Holes are nested", "ada lubang (hole) di dalam lubang lain"),
    ("Interior is disconnected", "lubang-lubang memotong bagian dalam poligon menjadi beberapa bagian terpisah"),
    ("Nested shells", "MultiPolygon berisi poligon yang berada di dalam poligon lain (nested shells)"),
    ("Duplicate Rings", "ada cincin (ring) yang tercatat dua kali"),
    ("Invalid Coordinate", "ada koordinat yang bukan angka (NaN/Infinity)"),
    ("Ring is not closed", "cincin poligon tidak tertutup (titik awal ≠ titik akhir)"),
    ("Self-touching ring", "cincin poligon menyentuh dirinya sendiri di satu titik"),
]


def _fmt(x: Any, y: Any) -> str:
    try:
        return f"({float(x):.7f}, {float(y):.7f})"
    except (TypeError, ValueError):
        return f"({x!r}, {y!r})"


def _expected_label(target: str) -> str:
    target = target.upper()
    family = target.removeprefix("MULTI")
    names = {"POINT": ("titik", "Point"), "LINESTRING": ("garis", "LineString"), "POLYGON": ("poligon", "Polygon")}
    if family not in names:
        return target or "geometri"
    word, gj = names[family]
    return f"{word} ({gj}/Multi{gj})" if target.startswith("MULTI") else f"{word} tunggal ({gj})"


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _positions(gtype: str, coords: Any):
    """(path, posisi) untuk setiap posisi koordinat, mengikuti kedalaman tipe GeoJSON."""
    depth = {"Point": 0, "MultiPoint": 1, "LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}[gtype]

    def walk(node, d, path):
        if d == 0:
            yield path, node
            return
        if not isinstance(node, (list, tuple)):
            raise ValueError(f"bagian koordinat {_path(path)} seharusnya berupa daftar (array), tetapi berisi {node!r}")
        for i, child in enumerate(node):
            yield from walk(child, d - 1, path + (i,))

    yield from walk(coords, depth, ())


def _path(path: tuple) -> str:
    return "[" + "][".join(str(p) for p in path) + "]" if path else "[]"


def _check_positions(gtype: str, coords: Any) -> str | None:
    if coords is None or coords == []:
        return f"Geometri {gtype} tidak punya koordinat (coordinates kosong)."
    for path, pos in _positions(gtype, coords):
        where = f"koordinat ke-{path[-1] + 1}" if path else "koordinat"
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return f"{where.capitalize()} {_path(path)} tidak lengkap: {pos!r} (harus [bujur, lintang])."
        x, y = pos[0], pos[1]
        if not (_is_number(x) and _is_number(y)):
            return (f"{where.capitalize()} {_path(path)} berisi nilai bukan angka: {list(pos[:2])!r}. "
                    "Pastikan koordinat berupa angka desimal, bukan teks/kosong.")
        if not (math.isfinite(x) and math.isfinite(y)):
            return f"{where.capitalize()} {_path(path)} bernilai NaN/Infinity: {list(pos[:2])!r}."
        if abs(x) > 180 or abs(y) > 90:
            swapped = abs(y) <= 180 and abs(x) <= 90
            hint = (" Kemungkinan urutan sumbu terbalik (lintang, bujur); GeoJSON wajib [bujur, lintang]."
                    if swapped else " Kemungkinan file masih dalam proyeksi meter (mis. UTM) tanpa info crs.")
            return (f"{where.capitalize()} {_path(path)} = {_fmt(x, y)} di luar rentang WGS84 "
                    f"(bujur -180..180, lintang -90..90).{hint}")
    return None


def _check_parts(gtype: str, coords: list) -> str | None:
    """Jumlah titik garis/ring dan ring tertutup (dicek sebelum shapely agar pesannya jelas)."""
    if gtype in ("LineString", "MultiLineString"):
        lines = [coords] if gtype == "LineString" else coords
        for n, line in enumerate(lines, start=1):
            unique = {tuple(p[:2]) for p in line}
            label = "Garis" if gtype == "LineString" else f"Garis ke-{n}"
            if len(line) < 2 or len(unique) < 2:
                return (f"{label} hanya punya {len(unique)} titik unik (dari {len(line)} titik); garis minimal 2 titik "
                        "berbeda. Hapus fitur ini atau gambar ulang garisnya.")
    if gtype in ("Polygon", "MultiPolygon"):
        polygons = [coords] if gtype == "Polygon" else coords
        for pn, rings in enumerate(polygons, start=1):
            if not rings:
                return f"Poligon ke-{pn} tidak punya cincin (ring) sama sekali."
            for rn, ring in enumerate(rings):
                ring_label = ("cincin luar" if rn == 0 else f"lubang (hole) ke-{rn}") + \
                             (f" poligon ke-{pn}" if gtype == "MultiPolygon" else "")
                unique = {tuple(p[:2]) for p in ring}
                if len(unique) < 3:
                    return (f"{ring_label.capitalize()} hanya punya {len(unique)} titik unik (dari {len(ring)} titik); "
                            "poligon minimal 3 titik berbeda + titik penutup (luasnya nol / titik dobel). "
                            "Hapus fitur ini atau gambar ulang poligonnya.")
                if tuple(ring[0][:2]) != tuple(ring[-1][:2]):
                    return (f"{ring_label.capitalize()} tidak tertutup: titik awal {_fmt(*ring[0][:2])} berbeda dengan "
                            f"titik akhir {_fmt(*ring[-1][:2])}. {FIX_HINT}")
                if len(ring) < 4:
                    return (f"{ring_label.capitalize()} hanya punya {len(ring)} titik; ring poligon minimal 4 titik "
                            "(termasuk titik penutup).")
    return None


def _translate_validity(reason: str) -> str:
    match = re.match(r"^(.*?)\[\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s*\]", reason)
    head, loc = (match.group(1).strip(), _fmt(match.group(2), match.group(3))) if match else (reason, None)
    text = next((txt for key, txt in GEOS_REASONS if head.lower().startswith(key.lower())), f"geometri tidak valid ({head})")
    return text + (f" di sekitar koordinat {loc}" if loc else "")


def explain_geometry(geometry: Any, target_type: str, layer: str | None = None) -> str:
    """Alasan rinci kenapa `geometry` (GeoJSON) tidak bisa dipakai untuk kolom bertipe `target_type` (nama PostGIS)."""
    target = (target_type or "").upper()
    family = target.removeprefix("MULTI")
    expected = _expected_label(target)
    need = f"Layer {layer} membutuhkan {expected}" if layer else f"Layer ini membutuhkan {expected}"
    if geometry is None or geometry == {}:
        return f"Geometri kosong (null): fitur ini hanya berisi atribut tanpa bentuk. {need}. " \
               "Gambar/isi geometrinya di QGIS atau hapus fitur ini dari file."
    if not isinstance(geometry, dict):
        return f"Geometri bukan objek GeoJSON (isi: {str(geometry)[:80]!r}). {need}."
    gtype = geometry.get("type")
    if gtype == "_GAGAL_KONVERSI":
        return (f"Koordinat gagal dikonversi dari EPSG:{geometry.get('epsg')} ke WGS84 (EPSG:4326). "
                "Periksa sistem koordinat (crs) file, atau export ulang dalam EPSG:4326.")
    if not gtype:
        return f"Objek geometri tidak punya atribut 'type'. {need}."
    if gtype == "GeometryCollection":
        return (f"Tipe GeometryCollection tidak didukung. {need}. "
                "Pecah fitur ini (QGIS: Multipart to Singleparts) dan simpan hanya bagian yang sesuai.")
    if gtype not in GEOJSON_TYPES:
        return f"Tipe geometri '{gtype}' tidak dikenal (harus salah satu dari: {', '.join(sorted(GEOJSON_TYPES))}). {need}."

    gfamily = gtype.upper().removeprefix("MULTI")
    if family and gfamily != family:
        return (f"Tipe geometri {gtype} tidak sesuai kategori. {need}. "
                "Pastikan file yang diunggah sesuai kategori yang dipilih, atau konversi tipenya di QGIS.")
    if family and target == family and gtype.upper() == f"MULTI{family}":
        coords = geometry.get("coordinates") or []
        n = len(coords) if isinstance(coords, list) else 0
        return (f"Tipe {gtype} (berisi {n} bagian) tidak diterima: layer hanya menerima satu {expected} per fitur. "
                "Pecah dengan QGIS: Vector > Geometry Tools > Multipart to Singleparts.")

    coords = geometry.get("coordinates")
    try:
        problem = _check_positions(gtype, coords)
    except ValueError as exc:
        return f"Struktur koordinat {gtype} rusak: {exc}."
    if problem:
        return problem
    problem = _check_parts(gtype, coords)
    if problem:
        return problem

    try:
        geom = shape(geometry)
    except (ShapelyError, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        return f"Struktur geometri {gtype} tidak bisa dibaca: {exc}. Export ulang file dari QGIS sebagai GeoJSON."
    if geom.is_empty:
        return f"Geometri {gtype} kosong (tidak berisi koordinat). Gambar ulang atau hapus fitur ini."
    if not geom.is_valid:
        detail = _translate_validity(explain_validity(geom))
        try:
            fixed = make_valid(geom)
            kinds = sorted({p.geom_type for p in getattr(fixed, "geoms", [fixed])})
        except (ShapelyError, ValueError):
            kinds = []
        tail = "" if any(k.upper().removeprefix("MULTI") == family for k in kinds) else (
            f" Perbaikan otomatis (make_valid) hanya menghasilkan {', '.join(kinds) or 'geometri kosong'} "
            f"— tidak ada {expected} yang tersisa (kemungkinan bentuknya runtuh/luas nol).")
        return f"Geometri tidak valid: {detail}.{tail} {FIX_HINT}"
    try:
        area_zero = gfamily == "POLYGON" and shapely.area(geom) == 0
    except (ShapelyError, ValueError):
        area_zero = False
    if area_zero:
        return f"Poligon luasnya nol (semua titik segaris). {FIX_HINT}"
    return (f"Geometri {gtype} tidak bisa disimpan. {need}. "
            f"Periksa bentuk dan tipe geometrinya di QGIS. {FIX_HINT}")
