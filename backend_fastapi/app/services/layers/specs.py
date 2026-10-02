"""
Spesifikasi layer spasial bawaan (handler LEGACY di spatial.layer_types).

Di backend lama tiap layer punya service & router sendiri yang ~95% identik.
Sekarang satu spesifikasi per layer dipakai oleh satu service & satu router
factory. Menambah layer bawaan cukup menambah entri di LAYER_SPECS.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    column: str                     # kolom fisik di tabel v3
    output: str                     # nama field di response (dipertahankan dari API lama)
    props: tuple[str, ...]          # nama properti GeoJSON yang dicoba berurutan
    kind: str = "text"              # text | int | float | ref:<tabel ref>
    non_negative: bool = False


@dataclass(frozen=True)
class LayerSpec:
    code: str
    label: str
    table: str                      # schema.tabel
    geometry_type: str              # tipe PostGIS kolom geom
    columns: tuple[Column, ...] = field(default_factory=tuple)
    upload_label: str = ""          # dipakai di nama key statistik lama, mis. 'slope' -> total_data_slope
    unique_objectid: bool = True    # ada UNIQUE (period, objectid)

    @property
    def derived(self) -> tuple[tuple[str, str], ...]:
        """
        Ukuran yang dulu disimpan dari file (Luas, Shape_Area, Shape_Leng, Panjang) tapi tidak punya kolom
        di v3 -> dihitung dari geometri (geography, satuan meter) saat ditampilkan.
        """
        if self.geometry_type.endswith("POLYGON"):
            return (
                ("luas", "round((ST_Area(t.geom::geography) / 10000)::numeric, 4)"),        # hektar
                ("shape_area", "round(ST_Area(t.geom::geography)::numeric, 2)"),              # m2
                ("shape_leng", "round(ST_Perimeter(t.geom::geography)::numeric, 2)"),         # m
            )
        if self.geometry_type.endswith("LINESTRING"):
            return (("panjang", "round(ST_Length(t.geom::geography)::numeric, 2)"),)          # m
        return ()

    @property
    def tipe_upload(self) -> str:
        return f"SPATIAL_{self.geometry_type}_{self.code.upper()}"


OBJECTID = Column("objectid", "objectid", ("OBJECTID", "ObjectID", "objectid"), "int")

LAYER_SPECS: dict[str, LayerSpec] = {
    spec.code: spec
    for spec in (
        LayerSpec(
            code="slope", label="Slope / Kelerengan", table="spatial.slope_polygons", geometry_type="MULTIPOLYGON",
            columns=(OBJECTID,
                     Column("category", "kategori", ("Kategori",)),
                     Column("slope_class", "kelerengan", ("Kelerengan", "Slope"))),
        ),
        LayerSpec(
            code="landuse", label="Land Use", table="spatial.landuse_polygons", geometry_type="MULTIPOLYGON",
            columns=(OBJECTID,
                     Column("landuse", "landuse", ("Landuse", "LandUse")),
                     Column("landuse_class", "landuse_class", ("Class", "Landuse_Class")),
                     Column("ownership", "ownership", ("Ownership",))),
        ),
        LayerSpec(
            code="jalan", label="Jalan", table="spatial.roads", geometry_type="MULTILINESTRING",
            columns=(OBJECTID,
                     Column("category", "kategori", ("Kategori",)),
                     Column("width_m", "lebar", ("Lebar", "Width"), "float", non_negative=True),
                     Column("ownership", "ownership", ("Ownership",))),
        ),
        LayerSpec(
            code="jembatan", label="Jembatan", table="spatial.bridges", geometry_type="POINT",
            columns=(OBJECTID, Column("category", "kategori", ("Kategori",))),
        ),
        LayerSpec(
            code="tph", label="TPH", table="spatial.tph_points", geometry_type="POINT",
            columns=(Column("category_id", "kategori", ("Kategori",), "ref:tph_categories"),),
            unique_objectid=False,
        ),
    )
}

# Pokok sawit punya model 2 tabel (palm_trees + tree_censuses) -> ditangani service khusus.
SAWIT_LABEL = "Pokok Sawit"
