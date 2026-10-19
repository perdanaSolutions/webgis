"""
Resolver id master & referensi untuk proses upload (dimuat sekali per upload, lalu lookup di memori).

Kunci blok di v3: estates.code unik global, divisions unik per (estate, code),
blocks unik per (division, code). Blok dicari lewat (estate, afdeling, blok); bila
tidak cocok persis, lewat kunci resmi UnitCode + Blok (estate + kode blok) asalkan
hasilnya tepat satu blok -- afdeling di file boleh berbeda dari master.
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.geojson import to_ewkb
from app.utils.parsing import clean_str, norm_key

ALIAS_TABLES = {"seed_varieties", "soil_types", "topography_types", "rotation_statuses"}


@dataclass
class BlockIndex:
    by_path: dict[tuple[int, str, str], int] = field(default_factory=dict)   # (estate_id, div, blok) -> block_id
    estate_ids: dict[str, int] = field(default_factory=dict)                  # kode/singkatan/nama estate -> id
    by_code: dict[str, list[int]] = field(default_factory=dict)               # kode blok -> [block_id]
    by_estate_block: dict[tuple[int, str], list[int]] = field(default_factory=dict)  # (estate_id, blok) -> [block_id]
    division_by_block: dict[int, str] = field(default_factory=dict)          # block_id -> kode afdeling master
    company_by_block: dict[int, str] = field(default_factory=dict)            # block_id -> kode PT (master.companies)
    group_by_block: dict[int, str | None] = field(default_factory=dict)       # block_id -> kode grup PT (TPA/SGA)
    area_by_block: dict[int, str | None] = field(default_factory=dict)        # block_id -> kode area estate saat ini
    estate_by_block: dict[int, int] = field(default_factory=dict)             # block_id -> estate_id
    divisions: set[tuple[int, str]] = field(default_factory=set)              # (estate_id, afdeling) yang ada di master

    @classmethod
    def load(cls, db: Session) -> "BlockIndex":
        index = cls()
        for r in db.execute(text("SELECT id, code, short_name, name FROM master.estates")).mappings():
            for key in (r["code"], r["short_name"], r["name"]):
                if key:
                    index.estate_ids.setdefault(norm_key(key), r["id"])
        for r in db.execute(text("SELECT estate_id, code FROM master.divisions")).mappings():
            index.divisions.add((r["estate_id"], norm_key(r["code"])))
        for r in db.execute(text("""
            SELECT bl.id, bl.code AS block_code, dv.code AS division_code, dv.estate_id, co.code AS company_code,
                   gr.code AS group_code, ar.code AS area_code
            FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id JOIN master.companies co ON co.id = es.company_id
            LEFT JOIN master.groups gr ON gr.id = co.group_id
            LEFT JOIN master.areas ar ON ar.id = es.area_id
        """)).mappings():
            index.company_by_block[r["id"]] = r["company_code"]
            index.group_by_block[r["id"]] = r["group_code"]
            index.area_by_block[r["id"]] = r["area_code"]
            index.estate_by_block[r["id"]] = r["estate_id"]
            index.add(r["estate_id"], r["division_code"], r["block_code"], r["id"])
        return index

    def estate_id(self, *refs: Any) -> int | None:
        for ref in refs:
            if ref and (found := self.estate_ids.get(norm_key(ref))):
                return found
        return None

    def miss_cause(self, estate_refs: tuple, division: Any) -> str:
        """Kenapa blok tidak ketemu: estate, afdeling, atau bloknya yang tidak ada di master."""
        estate_id = self.estate_id(*estate_refs)
        if estate_id is None:
            return "estate tidak dikenal di master"
        if not division or (estate_id, norm_key(division)) not in self.divisions:
            return "afdeling tidak ada di estate ini"
        return "blok tidak ada di afdeling ini"

    def resolve(self, estate_refs: tuple, division: Any, block: Any, allow_code_only: bool = False) -> int | None:
        block_key = norm_key(block)
        if not block_key:
            return None
        estate_id = self.estate_id(*estate_refs)
        if estate_id and division:
            found = self.by_path.get((estate_id, norm_key(division), block_key))
            if found:
                return found
        if estate_id:  # kunci resmi UnitCode + Blok, hanya bila tidak ambigu (blok kembar di beberapa afdeling)
            candidates = self.by_estate_block.get((estate_id, block_key), [])
            if len(candidates) == 1:
                return candidates[0]
        if allow_code_only:
            candidates = self.by_code.get(block_key, [])
            if len(candidates) == 1:
                return candidates[0]
        return None

    def add(self, estate_id: int, division: str, block: str, block_id: int) -> None:
        self.by_path[(estate_id, norm_key(division), norm_key(block))] = block_id
        if block_id not in self.by_code.setdefault(norm_key(block), []):
            self.by_code[norm_key(block)].append(block_id)
        if block_id not in self.by_estate_block.setdefault((estate_id, norm_key(block)), []):
            self.by_estate_block[(estate_id, norm_key(block))].append(block_id)
        self.estate_by_block[block_id] = estate_id
        self.division_by_block[block_id] = division

    def duplicate_divisions(self, estate_refs: tuple, block: Any) -> list[str]:
        """Afdeling master bila estate + kode blok menunjuk lebih dari satu blok (blok kembar), selain itu []."""
        estate_id = self.estate_id(*estate_refs)
        candidates = self.by_estate_block.get((estate_id, norm_key(block)), []) if estate_id else []
        return sorted(self.division_by_block[c] for c in candidates) if len(candidates) > 1 else []

    def other_division(self, block_id: int, division: Any) -> str | None:
        """Afdeling master blok bila berbeda dari afdeling di file (blok ditemukan lewat UnitCode + Blok)."""
        current = self.division_by_block.get(block_id)
        if division and current and norm_key(current) != norm_key(division):
            return current
        return None


def locate_blocks_by_geometry(db: Session, items: list[tuple[str, int | None]]) -> list[int | None]:
    """
    Cadangan saat label Estate/Afdeling/Blok di file tidak cocok dengan master:
    cari blok yang batasnya (versi terbaru) bersinggungan dengan geometri fitur.
    Jika estate fitur dikenali, hanya blok di estate itu yang dipertimbangkan.
    Polygon memilih blok dengan irisan terluas; titik/garis memilih yang bersinggungan.

    `items` = [(hex_ewkb | objek shapely, estate_id | None)], hasil berurutan sesuai input.
    """
    if not items:
        return []
    rows = db.execute(
        text("""
            WITH f AS (
                SELECT i, CAST(hex AS geometry) AS g, est
                FROM unnest(CAST(:hexes AS text[]), CAST(:ests AS bigint[])) WITH ORDINALITY AS t(hex, est, i)
            ),
            latest AS (
                SELECT DISTINCT ON (bb.block_id) bb.block_id, bb.geom, dv.estate_id
                FROM spatial.block_boundaries bb
                JOIN master.blocks bl ON bl.id = bb.block_id
                JOIN master.divisions dv ON dv.id = bl.division_id
                ORDER BY bb.block_id, bb.period DESC
            )
            SELECT f.i, (
                SELECT l.block_id FROM latest l
                WHERE ST_Intersects(l.geom, f.g) AND (f.est IS NULL OR l.estate_id = f.est)
                ORDER BY CASE WHEN GeometryType(f.g) LIKE '%POLYGON' THEN ST_Area(ST_Intersection(l.geom, f.g)) ELSE 0 END DESC,
                         l.block_id
                LIMIT 1
            ) AS block_id
            FROM f ORDER BY f.i
        """),
        {"hexes": [h if isinstance(h, str) else to_ewkb(h) for h, _ in items], "ests": [e for _, e in items]},
    ).all()
    return [r.block_id for r in rows]


@dataclass
class BlockMatchReport:
    missing: int = 0
    spatial_matches: int = 0
    unmatched_samples: list[str] = field(default_factory=list)
    corrections: dict[str, int] = field(default_factory=dict)  # "label file -> label master" : jumlah fitur

    def as_dict(self) -> dict:
        return {
            "dicocokkan_spasial": self.spatial_matches,
            "koreksi_label_blok": [{"label_file": k.split(" -> ")[0], "blok_master": k.split(" -> ")[1], "jumlah_data": n}
                                   for k, n in self.corrections.items()],
        }


def block_label(keys: tuple) -> str:
    """Label 'estate/afdeling/blok' dari keys `geojson_block_keys` (untuk pesan ke pengguna)."""
    estate_refs, division, block = keys
    estate = next((e for e in estate_refs if e), "-")
    return f"{estate}/{division}/{block}"


def match_blocks(db: Session, index: BlockIndex, candidates: list[tuple[tuple, str]]) -> tuple[list[int | None], BlockMatchReport]:
    """
    Tentukan block_id untuk setiap (keys GeoJSON, hex EWKB):
    1) cocokkan label Estate/Afdeling/Blok ke master;
    2) yang gagal -> cari berdasarkan posisi geometri terhadap batas blok (estate yang sama).
    Koreksi label dicatat di laporan supaya pengguna tahu datanya perlu dibetulkan.
    """
    report = BlockMatchReport()
    block_ids = [index.resolve(*keys) for keys, _ in candidates]
    pending = [i for i, b in enumerate(block_ids) if b is None]
    if pending:
        located = locate_blocks_by_geometry(db, [(candidates[i][1], index.estate_id(*candidates[i][0][0])) for i in pending])
        found_ids = {b for b in located if b is not None}
        labels = dict(db.execute(text("""
            SELECT bl.id, es.code || '/' || dv.code || '/' || bl.code
            FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            WHERE bl.id = ANY(:ids)
        """), {"ids": list(found_ids)}).all()) if found_ids else {}
        for i, block_id in zip(pending, located):
            file_label = block_label(candidates[i][0])
            if block_id is None:
                report.missing += 1
                if file_label not in report.unmatched_samples and len(report.unmatched_samples) < 5:
                    report.unmatched_samples.append(file_label)
                continue
            block_ids[i] = block_id
            report.spatial_matches += 1
            key = f"{file_label} -> {labels[block_id]}"
            report.corrections[key] = report.corrections.get(key, 0) + 1
    return block_ids, report


def geojson_block_keys(properties: dict) -> tuple[tuple, Any, Any] | None:
    """Properti standar GeoJSON kebun: PT, EstID/Estate/Est, Afdeling, Blok."""
    estate_refs = (properties.get("EstID"), properties.get("Est"), properties.get("Estate"))
    division, block = properties.get("Afdeling"), properties.get("Blok")
    if not any(estate_refs) or not division:  # export landuse: atribut master blok ada di kolom *_2 bila polygon tanpa afdeling
        estate_refs = estate_refs if any(estate_refs) else (properties.get("EstID_2"), None, properties.get("Estate_2"))
        division = division or properties.get("Afdeling_2")
    if not any(estate_refs) or not division or not block:
        return None
    return estate_refs, division, block


class RefResolver:
    """
    Nama -> id untuk tabel ref.* (kolom nama `name`, kecuali planting_statuses = `code`).
    Menerapkan ref.value_aliases (mis. 'CSTR' -> 'COSTARIKA'), cocok tanpa beda huruf besar/kecil,
    dan (opsional) membuat nilai baru bila belum ada.
    """

    def __init__(self, db: Session, table: str, create_missing: bool = True):
        self.db, self.table, self.create_missing = db, table, create_missing
        self.column = "code" if table == "planting_statuses" else "name"
        self.created: list[str] = []
        self.unknown: list[str] = []  # nilai belum ada & tidak dibuat (create_missing=False, mis. saat analisis)
        self._by_raw: dict[Any, int | None] = {}
        self._ids = {
            norm_key(r[1]): r[0]
            for r in db.execute(text(f"SELECT id, {self.column} FROM ref.{table}"))
        }
        self._aliases = {}
        if table in ALIAS_TABLES:
            self._aliases = {
                norm_key(r[0]): r[1]
                for r in db.execute(text("SELECT alias, canonical FROM ref.value_aliases WHERE ref_table = :t"), {"t": table})
            }

    def resolve(self, value: Any) -> int | None:
        try:
            return self._by_raw[value]
        except (KeyError, TypeError):
            pass
        result = self._resolve(value)
        try:
            self._by_raw[value] = result
        except TypeError:  # nilai tidak hashable
            pass
        return result

    def _resolve(self, value: Any) -> int | None:
        name = clean_str(value)
        if name is None:
            return None
        name = self._aliases.get(norm_key(name), name)
        key = norm_key(name)
        if key in self._ids:
            return self._ids[key]
        if not self.create_missing:
            if name not in self.unknown:
                self.unknown.append(name)
            return None
        new_id = self.db.execute(
            text(f"INSERT INTO ref.{self.table} ({self.column}) VALUES (:v) RETURNING id"), {"v": name[:100]}
        ).scalar_one()
        self._ids[key] = new_id
        self.created.append(name)
        return new_id
