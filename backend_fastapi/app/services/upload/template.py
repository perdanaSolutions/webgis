"""
Standar format file GeoJSON per kategori upload (template + petunjuk), diturunkan dari aturan validasi
yang sama dengan analisis/simpan supaya tidak menyimpang:

- kolom blok: `geojson_block_keys` (EstID/Est/Estate, Afdeling, Blok) dan `block_upload_service._read_feature`;
- layer bawaan: `LAYER_SPECS` (nama properti, tipe, aturan >= 0, OBJECTID unik);
- pokok sawit: aturan `sawit_service._prepare` (OBJECTID, Kategori wajib; Diameter/Jarak >= 0);
- layer dinamis (GENERIC): skema kolom `spatial.layer_types` yang benar-benar ada di tabel.

Koordinat: EPSG:4326 (WGS84, [bujur, lintang] derajat). File dengan member `crs` lain (mis. UTM EPSG:32647)
juga diterima dan dikonversi otomatis; tanpa `crs`, koordinat wajib lon/lat.
"""
import json
from dataclasses import dataclass

from app.services.layers.specs import LAYER_SPECS, SAWIT_LABEL, LayerSpec
from app.services.upload.report import ESTATE_KEYS

CRS84 = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
# Contoh kode master (ganti dengan kode Estate/Afdeling/Blok yang terdaftar di master Anda).
EXAMPLE_BLOCKS = [("E001", "AFDI01", "F016"), ("E001", "AFDI01", "G007")]
BASE_LON, BASE_LAT = 101.4500, 0.5200  # sekitar Riau


@dataclass(frozen=True)
class Field:
    name: str
    required: bool
    type: str
    examples: tuple
    rule: str
    aliases: tuple[str, ...] = ()


def _block_fields(estate_keys: tuple[str, ...]) -> list[Field]:
    alt = "/".join(estate_keys[1:])
    return [
        Field(estate_keys[0], True, "teks", ("E001", "E001"),
              f"Kode/singkatan/nama estate sesuai master. Nama kolom alternatif: {alt}.", estate_keys[1:]),
        Field("Afdeling", True, "teks", ("AFDI01", "AFDI01"), "Kode afdeling sesuai master estate tersebut."),
        Field("Blok", True, "teks", ("F016", "G007"), "Kode blok sesuai master afdeling tersebut."),
    ]


def _geometry(geometry_type: str, n: int) -> dict:
    lon, lat = BASE_LON + n * 0.01, BASE_LAT + n * 0.01
    family = geometry_type.upper().removeprefix("MULTI")
    if family == "POINT":
        single = [round(lon, 6), round(lat, 6)]
    elif family == "LINESTRING":
        single = [[round(lon, 6), round(lat, 6)], [round(lon + 0.002, 6), round(lat + 0.001, 6)],
                  [round(lon + 0.004, 6), round(lat + 0.001, 6)]]
    else:
        d = 0.003
        single = [[[round(x, 6), round(y, 6)] for x, y in
                   ((lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat))]]
    if geometry_type.upper().startswith("MULTI"):
        return {"type": "Multi" + {"POINT": "Point", "LINESTRING": "LineString", "POLYGON": "Polygon"}[family],
                "coordinates": [single]}
    return {"type": {"POINT": "Point", "LINESTRING": "LineString", "POLYGON": "Polygon"}[family], "coordinates": single}


SPEC_EXAMPLES = {  # contoh nilai per properti utama (layer bawaan)
    "OBJECTID": (1, 2), "Kategori": ("Contoh A", "Contoh B"), "Kelerengan": ("0-8%", "8-15%"),
    "Landuse": ("Kebun Inti", "Kebun Inti"), "Class": ("TM", "TBM"), "Ownership": ("Inti", "Plasma"),
    "Lebar": (6.0, 4.5),
}
KIND_LABEL = {"text": "teks", "int": "bilangan bulat", "float": "angka desimal"}


def _spec_fields(spec: LayerSpec) -> list[Field]:
    fields = _block_fields(ESTATE_KEYS)
    for col in spec.columns:
        name = col.props[0]
        kind = "teks (nilai referensi)" if col.kind.startswith("ref:") else KIND_LABEL.get(col.kind, col.kind)
        rules = []
        if name == "OBJECTID":
            rules.append("Bilangan bulat; " + ("harus unik dalam satu periode (duplikat: hanya data terakhir dipakai)."
                                               if spec.unique_objectid else "boleh berulang."))
        if col.non_negative:
            rules.append("Harus >= 0 (nilai negatif ditolak NILAI_TIDAK_VALID).")
        if col.kind.startswith("ref:"):
            rules.append(f"Dicocokkan ke ref.{col.kind[4:]}; nilai baru otomatis ditambahkan saat simpan.")
        rules.append("Kosong diperbolehkan.")
        if len(col.props) > 1:
            rules.append("Nama kolom alternatif: " + "/".join(col.props[1:]) + ".")
        fields.append(Field(name, False, kind, SPEC_EXAMPLES.get(name, ("Contoh", "Contoh")), " ".join(rules),
                            col.props[1:]))
    return fields


def _sawit_fields() -> list[Field]:
    return _block_fields(ESTATE_KEYS) + [
        Field("OBJECTID", True, "bilangan bulat", (1, 2), "Wajib, unik per pokok dalam satu periode."),
        Field("Kategori", True, "teks (nilai referensi)", ("Normal", "Normal"),
              "Wajib. Kategori pokok, dicocokkan ke ref.tree_categories (nilai baru ditambahkan saat simpan)."),
        Field("Diameter", False, "angka desimal", (45.5, 50.0), "Opsional, >= 0."),
        Field("Jarak", False, "angka desimal", (9.0, 9.0), "Opsional, >= 0 (jarak tanam)."),
    ]


def _blok_fields() -> list[Field]:
    from app.services.block_upload_service import BLOCK_ESTATE_KEYS  # lazy: hindari import berat saat startup

    # Contoh dikosongkan: kolom organisasi bila diisi bisa MENGUBAH master (PT/grup/area/nama estate) saat simpan.
    opt = lambda name, rule, aliases=(): Field(name, False, "teks", ("", ""), rule, aliases)
    return _block_fields(BLOCK_ESTATE_KEYS) + [
        opt("PT", "Nama PT pemilik estate (dipakai bila master PT belum ada)."),
        opt("Company_Code", "Kode PT. Bila berbeda dengan master, master ikut diperbarui.", ("CompanyCode",)),
        opt("short_name_pt", "Singkatan PT (nama kolom tidak peka huruf besar/kecil); mengisi/mengganti master."),
        opt("Group", "Kode grup PT (mis. TPA/SGA); mengisi/mengganti grup PT di master.", ("Grup",)),
        opt("Area", "Kode area estate (maks. 50 karakter); mengisi/mengganti area estate di master."),
        opt("Estate", "Nama estate (bila kosong dipakai kode estate)."),
        opt("Kategori", "Tipe blok (ref.block_types).", ("TipeBlok", "Ownership")),
    ]


GENERIC_TYPES = {
    "smallint": ("bilangan bulat", (1, 2)), "integer": ("bilangan bulat", (1, 2)), "bigint": ("bilangan bulat", (1, 2)),
    "double precision": ("angka desimal", (1.5, 2.5)), "real": ("angka desimal", (1.5, 2.5)),
    "numeric": ("angka desimal", (1.5, 2.5)), "boolean": ("ya/tidak (true/false)", (True, False)),
    "date": ("tanggal (YYYY-MM-DD)", ("2026-01-31", "2026-01-31")),
}


def _generic_fields(layer: dict, columns: list[dict]) -> list[Field]:
    fields = _block_fields(ESTATE_KEYS) if layer.get("relasi_blok") else []
    for col in columns:
        label, ex = GENERIC_TYPES.get(col["data_type"], ("teks", ("Contoh", "Contoh")))
        fields.append(Field(col["property"], False, label, ex,
                            f"Opsional. Nilai yang tidak cocok tipe ({col['data_type']}) disimpan kosong."))
    return fields


@dataclass(frozen=True)
class Template:
    code: str
    label: str
    geometry_type: str
    fields: list
    notes: tuple[str, ...] = ()

    def feature_collection(self) -> dict:
        features = []
        for n in range(2):
            props = {f.name: f.examples[n] for f in self.fields}
            features.append({"type": "Feature", "properties": props, "geometry": _geometry(self.geometry_type, n)})
        return {"type": "FeatureCollection", "name": f"standar_{self.code}", "crs": CRS84, "features": features}

    def geojson_bytes(self) -> bytes:
        return json.dumps(self.feature_collection(), ensure_ascii=False, indent=2).encode()

    def guide(self) -> str:
        family = self.geometry_type.upper()
        lines = [
            f"# Standar Format GeoJSON - {self.label} (kategori: {self.code})", "",
            "## Ketentuan file",
            "- Format: GeoJSON FeatureCollection (.geojson / .json), satu Feature per data.",
            "- Sistem koordinat: EPSG:4326 / WGS84, urutan [bujur, lintang] dalam derajat "
            "(Indonesia: bujur 95..141, lintang -11..6). File dengan member `crs` lain (mis. UTM) dikonversi otomatis.",
            f"- Tipe geometri: {family} (tipe tunggal otomatis dijadikan Multi bila perlu). "
            "Geometri kosong/tipe lain ditolak GEOMETRI_TIDAK_VALID.",
            "- Poligon harus tertutup, minimal 3 titik berbeda, tidak berpotongan sendiri "
            "(perbaiki di QGIS: Vector > Geometry Tools > Fix Geometries).",
            "- Nama kolom ditulis PERSIS seperti di bawah (huruf besar/kecil berpengaruh).",
            *[f"- {n}" for n in self.notes], "",
            "## Kolom (properties)", "",
            "| Nama kolom | Wajib | Tipe | Contoh | Aturan |", "|---|---|---|---|---|",
        ]
        for f in self.fields:
            lines.append(f"| {f.name} | {'Wajib' if f.required else 'Opsional'} | {f.type} | {f.examples[0] if f.examples[0] != '' else '(kosong)'} | {f.rule} |")
        lines += ["", "Kode Estate/Afdeling/Blok pada contoh hanyalah ilustrasi; ganti dengan kode yang terdaftar di master."]
        return "\n".join(lines) + "\n"


BLOCK_NOTE = ("Estate/Afdeling/Blok yang tidak cocok master dicocokkan ulang dari posisi geometri terhadap batas blok; "
              "bila tetap tidak ditemukan -> BLOK_TIDAK_DITEMUKAN.")


def builtin_template(code: str) -> Template | None:
    if code == "blok":
        return Template("blok", "Blok Kebun", "MULTIPOLYGON", _blok_fields(),
                        ("Beberapa fitur dengan Estate/Afdeling/Blok sama digabung menjadi satu batas blok.",
                         "Blok yang belum ada di master akan dibuat otomatis saat simpan."))
    if code == "sawit":
        return Template("sawit", SAWIT_LABEL, "POINT", _sawit_fields(), (BLOCK_NOTE,))
    if code in LAYER_SPECS:
        spec = LAYER_SPECS[code]
        return Template(code, spec.label, spec.geometry_type, _spec_fields(spec), (BLOCK_NOTE,))
    return None


def generic_template(layer: dict, columns: list[dict]) -> Template:
    notes = (BLOCK_NOTE,) if layer.get("relasi_blok") else ("Layer ini tidak terikat blok; kolom Estate/Afdeling/Blok tidak diperlukan.",)
    return Template(layer["kode"], layer.get("nama") or layer["kode"], layer["geometry_type"],
                    _generic_fields(layer, columns), notes)
