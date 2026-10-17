"""
Upload GeoJSON batas blok: mendaftarkan master (PT -> estate -> afdeling -> blok)
yang belum ada, lalu menyimpan poligon ke spatial.block_boundaries per periode.

Catatan model v3:
- Master tidak berperiode; hanya batas blok yang berperiode (PK block_id + period),
  jadi upload ulang periode yang sama menimpa poligon blok tersebut.
- Area TIDAK disimpan di master (area melekat ke area statement), sehingga
  properti `Area` hanya dilaporkan di ringkasan analisis.
- PT baru dibuat dengan kode dari properti `Company_Code`; bila tidak ada,
  kode = nama PT yang dinormalisasi (maks 20 karakter).
- Satu blok boleh terdiri dari beberapa fitur (blok terpecah): poligonnya
  digabung menjadi satu MultiPolygon sebelum disimpan.
- Struktur v2: properti `Group` adalah sumber resmi grup PT (companies.group_id)
  dan properti `Area` sumber resmi area saat ini estate (estates.area_id). Nilai
  master diisi/diganti sesuai file; PT/estate yang nilainya berbeda-beda di dalam
  satu file tidak diubah.
"""
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.data_version import GEOJSON, bump
from app.services.upload import quarantine
from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload.progress import SILENT, Progress
from app.services.upload.resolvers import BlockIndex, RefResolver
from app.utils.geojson import merge_polygons, parse_features, prepare_geometry, to_ewkb
from app.utils.parsing import clean_str, norm_key
from app.utils.period import period_label, to_period
from app.utils.sql import quote_table

TARGET_TABLE = "spatial.block_boundaries"


@dataclass
class BlockFeature:
    area: str | None
    company: str | None
    company_code: str | None
    group: str | None  # kode grup huruf besar (TPA/SGA)
    estate_code: str
    estate_name: str
    division: str
    block: str
    block_type: str | None
    geom: object | None  # MultiPolygon shapely


def _read_feature(props: dict, geometry: dict | None) -> BlockFeature | None:
    estate_code = clean_str(props.get("Est_ID") or props.get("EstID") or props.get("Est") or props.get("Estate"))
    division, block = clean_str(props.get("Afdeling")), clean_str(props.get("Blok"))
    if not (estate_code and division and block):
        return None
    group = clean_str(props.get("Group") or props.get("Grup"))
    return BlockFeature(
        area=area[:50] if (area := clean_str(props.get("Area"))) else None,
        company=clean_str(props.get("PT")),
        company_code=clean_str(props.get("Company_Code") or props.get("CompanyCode")),
        group=group.upper()[:20] if group else None,
        estate_code=estate_code,
        estate_name=clean_str(props.get("Estate")) or estate_code,
        division=division,
        block=block,
        block_type=clean_str(props.get("Kategori") or props.get("TipeBlok") or props.get("Ownership")),
        geom=prepare_geometry(geometry, "MULTIPOLYGON"),
    )


def _block_key(item: BlockFeature) -> tuple[str, str, str]:
    return norm_key(item.estate_code), norm_key(item.division), norm_key(item.block)


Ref = dict[str, tuple[int, str]]  # kode/nama ternormalisasi -> (id, kode master)


def _ref_lookup(db: Session, table: str) -> Ref:
    """Grup/area/PT dicocokkan lewat kode atau nama (norm_key), sama seperti importer transaksi."""
    lookup: Ref = {}
    for ref_id, code, name in db.execute(text(f"SELECT id, code, name FROM {table}")):
        for key in (code, name):
            if key:
                lookup.setdefault(norm_key(key), (ref_id, code))
    return lookup


def _company_owner(companies: Ref):
    """PT fitur = PT master hasil pencocokan Company_Code lalu nama PT (kunci 'co:<id>'), atau label file bila PT baru."""
    def owner_of(item: BlockFeature) -> tuple[str, str] | None:
        labels = [label for label in (item.company_code, item.company) if label]
        for label in labels:
            if (found := companies.get(norm_key(label))):
                return f"co:{found[0]}", found[1]
        return (norm_key(labels[0]), labels[0]) if labels else None
    return owner_of


def _estate_of(item: BlockFeature) -> tuple[str, str]:
    return norm_key(item.estate_code), item.estate_code


def _plan(items: list[BlockFeature], owner_of, value_of, master: dict[str, str | None], refs: Ref) -> list[dict]:
    """
    Rencana nilai master (grup PT / area estate) dari file, dibandingkan dengan master.
    Nilai file diganti kode master bila sudah terdaftar (kode atau nama), jadi 'KUTIM 2' = 'KUTIM2'.
    status: SAMA, DIISI (master belum punya nilai), BERUBAH, BERTENTANGAN_DI_FILE (lebih dari satu nilai di file).
    """
    in_file: dict[str, tuple[str, set[str]]] = {}
    for item in items:
        owner, value = owner_of(item), value_of(item)
        if owner and value:
            canonical = refs.get(norm_key(value), (None, value))[1]
            in_file.setdefault(owner[0], (owner[1], set()))[1].add(canonical)
    plan = []
    for key, (label, values) in sorted(in_file.items()):
        current = master.get(key)
        if len(values) > 1:
            status = "BERTENTANGAN_DI_FILE"
        elif current is None:
            status = "DIISI"
        else:
            status = "SAMA" if norm_key(current) == norm_key(next(iter(values))) else "BERUBAH"
        plan.append({"key": key, "pemilik": label, "file": "/".join(sorted(values)), "master": current,
                     "status": status})
    return plan


def _org_plans(db: Session, items) -> tuple[dict[str, list[dict]], dict[str, Ref]]:
    """Rencana `grup` (per PT, dari Group) dan `area` (per estate, dari Area), beserta tabel pencocokannya."""
    items = list(items)
    refs = {"grup": _ref_lookup(db, "master.groups"), "area": _ref_lookup(db, "master.areas")}
    companies = _ref_lookup(db, "master.companies")
    company_groups = {f"co:{company_id}": group for company_id, group in db.execute(text(
        "SELECT co.id, gr.code FROM master.companies co LEFT JOIN master.groups gr ON gr.id = co.group_id"))}
    estate_areas = {norm_key(code): area for code, area in db.execute(text(
        "SELECT es.code, ar.code FROM master.estates es LEFT JOIN master.areas ar ON ar.id = es.area_id"))}
    plans = {
        "grup": _plan(items, _company_owner(companies), lambda i: i.group, company_groups, refs["grup"]),
        "area": _plan(items, _estate_of, lambda i: i.area, estate_areas, refs["area"]),
    }
    return plans, refs


# (kode peringatan, label pemilik untuk pesan) per jenis rencana
_PLAN_LABELS = {"grup": ("GRUP", "PT", "Grup"), "area": ("AREA", "estate", "Area")}


def _plan_warnings(kind: str, plan: list[dict], refs: Ref) -> list[dict]:
    code, owner, noun = _PLAN_LABELS[kind]
    by_status = {s: [p for p in plan if p["status"] == s] for s in ("DIISI", "BERUBAH", "BERTENTANGAN_DI_FILE")}
    new_codes = sorted({p["file"] for p in by_status["DIISI"] + by_status["BERUBAH"] if norm_key(p["file"]) not in refs})
    warnings = []
    if by_status["BERUBAH"]:
        listed = ", ".join(f"{p['pemilik']} ({p['master']} -> {p['file']})" for p in by_status["BERUBAH"])
        warnings.append({"kode": f"{code}_BERUBAH", "level": "PERINGATAN", "jumlah": len(by_status["BERUBAH"]),
                         "pesan": f"{noun} {owner} berikut akan DIGANTI sesuai file: {listed}."})
    if by_status["BERTENTANGAN_DI_FILE"]:
        listed = ", ".join(f"{p['pemilik']} ({p['file']})" for p in by_status["BERTENTANGAN_DI_FILE"])
        warnings.append({"kode": f"{code}_BERTENTANGAN", "level": "PERINGATAN",
                         "jumlah": len(by_status["BERTENTANGAN_DI_FILE"]),
                         "pesan": f"{owner} berikut punya lebih dari satu {noun.lower()} di file sehingga "
                                  f"{noun.lower()}nya TIDAK diubah: {listed}."})
    if new_codes:
        warnings.append({"kode": f"{code}_BARU", "level": "PERINGATAN", "jumlah": len(new_codes),
                         "pesan": f"{noun} berikut belum terdaftar dan akan DIBUAT otomatis: {', '.join(new_codes)}. "
                                  "Pastikan bukan salah ketik."})
    if by_status["DIISI"]:
        warnings.append({"kode": f"{code}_DIISI", "level": "INFO", "jumlah": len(by_status["DIISI"]),
                         "pesan": f"{len(by_status['DIISI'])} {owner} belum punya {noun.lower()} di master "
                                  "dan akan diisi sesuai file."})
    return warnings


DETAIL_LIMIT = 100  # batas jumlah baris per daftar detail di hasil analisis (total tetap dilaporkan)


def _missing_attributes(props: dict) -> list[str]:
    missing = []
    if not clean_str(props.get("Est_ID") or props.get("EstID") or props.get("Est") or props.get("Estate")):
        missing.append("Estate (Est_ID/EstID/Est/Estate)")
    if not clean_str(props.get("Afdeling")):
        missing.append("Afdeling")
    if not clean_str(props.get("Blok")):
        missing.append("Blok")
    return missing


EXPORT_KEYS = {"kode_est", "kode_afd", "kode_blok"}


def _wrong_file_hint(features: list[dict]) -> str:
    """Petunjuk tambahan saat tidak ada fitur valid: file hasil unduhan WebGIS atau bukan poligon."""
    keys = {k for f in features[:200] for k in (f.get("properties") or {})}
    types = {str((f.get("geometry") or {}).get("type")) for f in features[:200]}
    if EXPORT_KEYS <= keys:
        return (" File ini tampaknya hasil unduhan dari WebGIS (kolom kode_est/kode_afd/kode_blok), "
                "bukan file sumber batas blok.")
    if not types & {"Polygon", "MultiPolygon"}:
        return f" File ini tidak berisi poligon (tipe geometri: {', '.join(sorted(types))})."
    return ""


def _block_label(item: BlockFeature) -> str:
    return f"{item.estate_code}/{item.division}/{item.block}"


def analyze(db: Session, content: bytes, bulan: int, tahun: int, progress: Progress = SILENT) -> dict:
    """
    Analisis (tanpa menyimpan) file batas blok. Selain angka ringkas, dilaporkan juga
    rinciannya supaya pengunggah tahu fitur mana yang bermasalah dan apa akibatnya.
    Nomor fitur (`no_preview`) dimulai dari 1, sama dengan nomor baris di tabel preview FE.
    """
    period = to_period(bulan, tahun)
    label = period_label(period)
    progress.stage("membaca_file")
    features = parse_features(content)
    index = BlockIndex.load(db)
    existing_boundaries = set(db.execute(
        text("SELECT block_id FROM spatial.block_boundaries WHERE period = :p"), {"p": period}
    ).scalars())

    invalid_rows, invalid_geom_rows = [], []
    areas, companies = set(), set()
    # Satu blok bisa muncul di beberapa fitur; dikelompokkan per kunci estate/afdeling/blok.
    by_block: dict[tuple, dict] = {}
    progress.stage("validasi", total=len(features))
    for i, feature in enumerate(features):
        progress.step(i + 1)
        props = feature.get("properties") or {}
        item = _read_feature(props, feature.get("geometry"))
        if item is None:
            invalid_rows.append({"no_preview": i + 1, "atribut_kosong": _missing_attributes(props)})
            continue
        if item.geom is None:
            invalid_geom_rows.append({"no_preview": i + 1, "blok": _block_label(item)})
            continue
        areas.add(norm_key(item.area))
        companies.add(norm_key(item.company))
        key = _block_key(item)
        if key not in by_block:
            block_id = index.resolve((item.estate_code,), item.division, item.block)
            twins = index.duplicate_divisions((item.estate_code,), item.block) if block_id is None else []
            by_block[key] = {"item": item, "fitur": [], "block_id": block_id, "kembar": twins,
                             "status": "BLOK_KEMBAR" if twins else "BLOK_BARU" if block_id is None
                             else "DITIMPA" if block_id in existing_boundaries else "BARU",
                             # ditemukan lewat UnitCode + Blok di afdeling lain -> dipindah ke afdeling file
                             "afdeling_master": index.other_division(block_id, item.division) if block_id else None}
        by_block[key]["fitur"].append(i)
        by_block[key].setdefault("items", []).append(item)

    progress.stage("menyusun_laporan")
    twin_blocks = [b for b in by_block.values() if b["status"] == "BLOK_KEMBAR"]
    blocks = [b for b in by_block.values() if b["status"] != "BLOK_KEMBAR"]
    plans, refs = _org_plans(db, (item for b in blocks for item in b["items"]))
    company_owner = _company_owner(_ref_lookup(db, "master.companies"))
    group_of = {p["key"]: p["file"] for p in plans["grup"]}
    area_of = {p["key"]: p["file"] for p in plans["area"]}
    changed = {kind: sum(p["status"] in ("DIISI", "BERUBAH") for p in plan) for kind, plan in plans.items()}
    new_master = [b for b in blocks if b["status"] == "BLOK_BARU"]
    moved = [b for b in blocks if b["afdeling_master"]]
    overwritten = [b for b in blocks if b["status"] == "DITIMPA"]
    split = [b for b in blocks if len(b["fitur"]) > 1]
    valid_features = len(features) - len(invalid_rows) - len(invalid_geom_rows)

    per_estate: dict[str, dict] = {}
    for b in blocks:
        item = b["item"]
        row = per_estate.setdefault(norm_key(item.estate_code), {
            "estate": item.estate_code, "nama_estate": item.estate_name, "pt": item.company,
            "grup": group_of.get((company_owner(item) or ("",))[0]), "area": area_of.get(norm_key(item.estate_code)),
            "afdeling": set(), "jumlah_blok": 0, "batas_baru": 0, "batas_ditimpa": 0, "blok_baru_di_master": 0,
            "blok_terpecah": 0,
        })
        row["afdeling"].add(norm_key(item.division))
        row["jumlah_blok"] += 1
        row["batas_ditimpa" if b["status"] == "DITIMPA" else "batas_baru"] += 1
        row["blok_baru_di_master"] += b["status"] == "BLOK_BARU"
        row["blok_terpecah"] += len(b["fitur"]) > 1
    for code, row in per_estate.items():
        afdeling = len(row.pop("afdeling"))
        head = ("estate", "nama_estate", "pt", "grup", "area")
        per_estate[code] = {**{k: row[k] for k in head}, "jumlah_afdeling": afdeling,
                            **{k: v for k, v in row.items() if k not in head}}

    warnings = []
    if invalid_rows:
        warnings.append({
            "kode": "ATRIBUT_TIDAK_LENGKAP", "level": "PERINGATAN", "jumlah": len(invalid_rows),
            "pesan": f"{len(invalid_rows)} data tidak punya Estate/Afdeling/Blok lengkap dan akan DILEWATI. "
                     "Lengkapi atributnya di file sumber bila data ini memang blok.",
        })
    if invalid_geom_rows:
        warnings.append({
            "kode": "GEOMETRI_TIDAK_VALID", "level": "PERINGATAN", "jumlah": len(invalid_geom_rows),
            "pesan": f"{len(invalid_geom_rows)} data geometrinya kosong/bukan poligon dan akan DILEWATI.",
        })
    if split:
        total_split = sum(len(b["fitur"]) for b in split)
        warnings.append({
            "kode": "BLOK_TERPECAH", "level": "INFO", "jumlah": len(split),
            "pesan": f"{len(split)} blok terdiri dari lebih dari satu data (total {total_split} data). "
                     "Poligon tiap blok digabung menjadi satu saat disimpan. Periksa 'blok_terpecah' di rincian "
                     "bila ada yang seharusnya blok berbeda (salah label).",
        })
    for kind, plan in plans.items():
        warnings.extend(_plan_warnings(kind, plan, refs[kind]))
    if overwritten:
        warnings.append({
            "kode": "MENIMPA_DATA_LAMA", "level": "INFO", "jumlah": len(overwritten),
            "pesan": f"{len(overwritten)} blok sudah punya batas di periode {label}; batas lamanya akan diganti.",
        })
    if twin_blocks:
        warnings.append({
            "kode": "BLOK_KEMBAR_DI_MASTER", "level": "PERINGATAN", "jumlah": len(twin_blocks),
            "pesan": f"{len(twin_blocks)} blok punya kode yang di master tercatat di beberapa afdeling, dan afdeling "
                     "di file tidak sama dengan salah satunya. Blok ini DILEWATI (tidak dibuat blok baru) supaya "
                     "tidak ada salinan ketiga. Tentukan blok yang benar dulu (lihat 'blok_kembar_di_master').",
        })
    if moved:
        warnings.append({
            "kode": "BLOK_PINDAH_AFDELING", "level": "PERINGATAN", "jumlah": len(moved),
            "pesan": f"{len(moved)} blok sudah ada di master pada afdeling lain (dicocokkan lewat UnitCode + Blok) "
                     "dan akan DIPINDAH ke afdeling sesuai file. Periksa 'blok_pindah_afdeling' di rincian.",
        })
    if new_master:
        warnings.append({
            "kode": "BLOK_BARU_DI_MASTER", "level": "PERINGATAN", "jumlah": len(new_master),
            "pesan": f"{len(new_master)} blok belum terdaftar di master dan akan DIBUAT otomatis. "
                     "Pastikan kode estate/afdeling/blok-nya benar agar tidak membuat blok ganda.",
        })

    if not blocks:
        status = "TIDAK_ADA_DATA_VALID"
        conclusion = (f"Tidak ada data yang bisa disimpan dari {len(features)} data. Pastikan file berisi poligon batas "
                      "blok dengan atribut Est_ID/EstID, Afdeling, dan Blok.")
        conclusion += _wrong_file_hint(features)
    else:
        status = "SIAP_DENGAN_CATATAN" if any(w["level"] == "PERINGATAN" for w in warnings) else "SIAP"
        parts = [f"Dari {len(features)} data, {len(blocks)} blok akan disimpan untuk periode {label} "
                 f"({len(blocks) - len(overwritten)} batas baru, {len(overwritten)} menimpa batas lama)."]
        if invalid_rows or invalid_geom_rows:
            parts.append(f"{len(invalid_rows) + len(invalid_geom_rows)} data dilewati.")
        if split:
            parts.append(f"{len(split)} blok terdiri dari beberapa poligon dan akan digabung.")
        if twin_blocks:
            parts.append(f"{len(twin_blocks)} blok dilewati karena kodenya kembar di master.")
        if changed["grup"]:
            parts.append(f"Grup {changed['grup']} PT akan diisi/diganti.")
        if changed["area"]:
            parts.append(f"Area {changed['area']} estate akan diisi/diganti.")
        conclusion = " ".join(parts)

    return {
        "tipe_upload": "GEOMETRI_BLOK_AND_MASTER_DATA",
        "periode": label,
        "status_analisis": status,
        "kesimpulan": conclusion,
        "total_data": len(features),
        "data_valid": valid_features,
        "jumlah_blok_akan_disimpan": len(blocks),
        # Field lama (dipakai FE); dihitung per BLOK, bukan per data.
        "data_baru_di_periode_ini": len(blocks) - len(overwritten),
        "data_akan_ditimpa_di_periode_ini": len(overwritten),
        "blok_baru_di_master": len(new_master),
        "data_tidak_valid": len(invalid_rows),
        "data_geometri_invalid": len(invalid_geom_rows),
        "blok_terpecah": len(split),
        "ringkasan_struktur_data": {
            "jumlah_master_area": len(areas - {""}),
            "jumlah_perusahaan_pt": len(companies - {""}),
            "jumlah_estate": len(per_estate),
            "jumlah_afdeling": len({k[:2] for k in by_block}),
            "jumlah_blok": len(blocks),
        },
        "peringatan": warnings,
        "rincian": {
            "per_estate": sorted(per_estate.values(), key=lambda r: r["estate"]),
            "data_tidak_valid": invalid_rows[:DETAIL_LIMIT],
            "data_geometri_invalid": invalid_geom_rows[:DETAIL_LIMIT],
            "blok_terpecah": [
                {"blok": _block_label(b["item"]), "jumlah_data": len(b["fitur"]), "no_preview": [n + 1 for n in b["fitur"]]}
                for b in split[:DETAIL_LIMIT]
            ],
            "grup_pt": [{k: v for k, v in p.items() if k != "key"} for p in plans["grup"]],
            "area_estate": [{k: v for k, v in p.items() if k != "key"} for p in plans["area"]],
            "blok_akan_ditimpa": [_block_label(b["item"]) for b in overwritten[:DETAIL_LIMIT]],
            "blok_baru_di_master": [_block_label(b["item"]) for b in new_master[:DETAIL_LIMIT]],
            "blok_pindah_afdeling": [{"blok": _block_label(b["item"]), "afdeling_master": b["afdeling_master"]}
                                     for b in moved[:DETAIL_LIMIT]],
            "blok_kembar_di_master": [{"blok": _block_label(b["item"]), "afdeling_master": b["kembar"]}
                                      for b in twin_blocks[:DETAIL_LIMIT]],
        },
    }


@dataclass
class _MasterCache:
    companies: dict[str, int] = field(default_factory=dict)   # kode/nama ternormalisasi -> id
    estates: dict[str, tuple[int, int]] = field(default_factory=dict)  # kode estate -> (id, company_id)
    divisions: dict[tuple[int, str], int] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=lambda: {"perusahaan": 0, "estate": 0, "afdeling": 0, "blok": 0,
                                                              "blok_pindah_afdeling": 0})

    @classmethod
    def load(cls, db: Session) -> "_MasterCache":
        cache = cls()
        for r in db.execute(text("SELECT id, code, name FROM master.companies")).mappings():
            for key in (r["code"], r["name"]):
                if key:
                    cache.companies.setdefault(norm_key(key), r["id"])
        for r in db.execute(text("SELECT id, code, company_id FROM master.estates")).mappings():
            cache.estates[norm_key(r["code"])] = (r["id"], r["company_id"])
        for r in db.execute(text("SELECT id, estate_id, code FROM master.divisions")).mappings():
            cache.divisions[(r["estate_id"], norm_key(r["code"]))] = r["id"]
        return cache


def _ensure_master(db: Session, cache: _MasterCache, index: BlockIndex, block_type_id: int | None, item: BlockFeature) -> int:
    estate = cache.estates.get(norm_key(item.estate_code))
    if estate is None:
        code_key, name_key = norm_key(item.company_code), norm_key(item.company)
        if not (code_key or name_key):
            raise ValueError(f"Estate '{item.estate_code}' belum terdaftar dan properti PT/Company_Code kosong.")
        company_id = cache.companies.get(code_key) or cache.companies.get(name_key)
        if company_id is None:
            company_id = db.execute(
                text("INSERT INTO master.companies (code, name) VALUES (:code, :name) RETURNING id"),
                {"code": (item.company_code or name_key)[:20], "name": item.company},
            ).scalar_one()
            for key in (code_key, name_key):
                if key:
                    cache.companies[key] = company_id
            cache.created["perusahaan"] += 1
        estate_id = db.execute(
            text("INSERT INTO master.estates (company_id, code, name) VALUES (:c, :code, :name) RETURNING id"),
            {"c": company_id, "code": item.estate_code[:20], "name": item.estate_name[:100]},
        ).scalar_one()
        estate = (estate_id, company_id)
        cache.estates[norm_key(item.estate_code)] = estate
        index.estate_ids[norm_key(item.estate_code)] = estate_id
        cache.created["estate"] += 1

    estate_id = estate[0]
    division_id = cache.divisions.get((estate_id, norm_key(item.division)))
    if division_id is None:
        division_id = db.execute(
            text("INSERT INTO master.divisions (estate_id, code) VALUES (:e, :code) RETURNING id"),
            {"e": estate_id, "code": item.division[:20]},
        ).scalar_one()
        cache.divisions[(estate_id, norm_key(item.division))] = division_id
        cache.created["afdeling"] += 1

    block_id = index.resolve((item.estate_code,), item.division, item.block)
    if block_id is None:
        block_id = db.execute(
            text("INSERT INTO master.blocks (division_id, code, block_type_id) VALUES (:d, :code, :t) RETURNING id"),
            {"d": division_id, "code": item.block[:20], "t": block_type_id},
        ).scalar_one()
        index.add(estate_id, item.division, item.block, block_id)
        cache.created["blok"] += 1
        return block_id
    if index.other_division(block_id, item.division):  # ditemukan lewat UnitCode + Blok: ikuti afdeling di file
        db.execute(text("UPDATE master.blocks SET division_id = :d WHERE id = :id"), {"d": division_id, "id": block_id})
        index.add(estate_id, item.division, item.block, block_id)
        cache.created["blok_pindah_afdeling"] += 1
    if block_type_id is not None:
        db.execute(
            text("UPDATE master.blocks SET block_type_id = :t WHERE id = :id AND block_type_id IS DISTINCT FROM :t"),
            {"t": block_type_id, "id": block_id},
        )
    return block_id


def _apply_plan(db: Session, plan: list[dict], ref_table: str, refs: Ref, update_sql: str,
                owner_ids: dict[str, int]) -> tuple[list[str], list[dict]]:
    """Isi/ganti nilai master sesuai rencana (_plan); grup/area yang belum terdaftar (kode maupun nama) dibuat."""
    targets = [p for p in plan if p["status"] in ("DIISI", "BERUBAH") and p["key"] in owner_ids]
    created = []
    for p in targets:
        key = norm_key(p["file"])
        if key not in refs:
            ref_id = db.execute(text(f"INSERT INTO {ref_table} (code, name) VALUES (:c, :c) RETURNING id"),
                                {"c": p["file"]}).scalar_one()
            refs[key] = (ref_id, p["file"])
            created.append(p["file"])
        db.execute(text(update_sql), {"v": refs[key][0], "id": owner_ids[p["key"]]})
    return created, targets


def _apply_org(db: Session, cache: _MasterCache, plans: dict[str, list[dict]], refs: dict[str, Ref]) -> dict:
    """Grup PT dan area estate dari file. PT dikenali lewat id hasil pencocokan (atau kode/nama), estate lewat kode."""
    company_ids = {**cache.companies, **{f"co:{company_id}": company_id for company_id in set(cache.companies.values())}}
    groups_new, groups = _apply_plan(db, plans["grup"], "master.groups", refs["grup"],
                                     "UPDATE master.companies SET group_id = :v WHERE id = :id", company_ids)
    areas_new, areas = _apply_plan(db, plans["area"], "master.areas", refs["area"],
                                   "UPDATE master.estates SET area_id = :v WHERE id = :id",
                                   {key: ids[0] for key, ids in cache.estates.items()})

    def changes(targets):
        return [f"{p['pemilik']}: {p['master']} -> {p['file']}" for p in targets if p["status"] == "BERUBAH"]

    def conflicts(plan):
        return [p["pemilik"] for p in plan if p["status"] == "BERTENTANGAN_DI_FILE"]

    return {
        "grup_baru": groups_new,
        "grup_pt_diisi": sum(p["status"] == "DIISI" for p in groups),
        "grup_pt_diganti": changes(groups),
        "grup_pt_bertentangan_di_file": conflicts(plans["grup"]),
        "area_baru": areas_new,
        "area_estate_diisi": sum(p["status"] == "DIISI" for p in areas),
        "area_estate_diganti": changes(areas),
        "area_estate_bertentangan_di_file": conflicts(plans["area"]),
    }


def execute(db: Session, content: bytes, filename: str | None, bulan: int, tahun: int, user_id: UUID | None,
            progress: Progress = SILENT) -> dict:
    period = to_period(bulan, tahun)
    batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table=TARGET_TABLE, source_name=filename,
                           user_id=user_id, period=period, metadata={"layer": "blok"})
    progress.batch(batch_id)
    progress.stage("membaca_file")
    features = parse_features(content)
    index, cache = BlockIndex.load(db), _MasterCache.load(db)
    block_types = RefResolver(db, "block_types")

    invalid, failed, last_error = 0, 0, None
    saved_blocks: set[int] = set()
    rejected: list[quarantine.Rejected] = []
    # Fitur dikelompokkan per blok dulu supaya potongan poligon blok yang sama digabung, bukan saling menimpa.
    blocks: dict[tuple, dict] = {}
    progress.stage("validasi", total=len(features))
    for no, feature in enumerate(features, start=1):
        progress.step(no)
        props = feature.get("properties") or {}
        item = _read_feature(props, feature.get("geometry"))
        if item is None or item.geom is None:
            invalid += 1
            rejected.append(
                quarantine.Rejected(no, "ATRIBUT_BLOK_KOSONG", "Kosong: " + ", ".join(_missing_attributes(props)), feature)
                if item is None else
                quarantine.Rejected(no, "GEOMETRI_TIDAK_VALID", "Geometri kosong atau bukan poligon.", feature)
            )
            continue
        entry = blocks.setdefault(_block_key(item), {"item": item, "items": [], "features": []})
        entry["items"].append(item)
        entry["features"].append((no, feature))

    success = 0  # jumlah fitur yang tersimpan (potongan blok terpecah dihitung masing-masing)
    twin_skipped = 0
    progress.stage("menyimpan", total=len(blocks))
    for done, entry in enumerate(blocks.values(), start=1):
        progress.step(done)  # di luar savepoint: UploadCancelled tidak boleh tertangkap sebagai gagal per blok
        item = entry["item"]
        if index.resolve((item.estate_code,), item.division, item.block) is None and (
                twins := index.duplicate_divisions((item.estate_code,), item.block)):
            twin_skipped += len(entry["features"])
            reason = f"Blok {item.block} di master tercatat di afdeling {', '.join(twins)}; tentukan blok yang benar dulu."
            rejected.extend(quarantine.Rejected(no, "BLOK_KEMBAR_DI_MASTER", reason, f) for no, f in entry["features"])
            continue
        block_type_id = block_types.resolve(item.block_type)  # di luar savepoint: id ref tetap valid
        savepoint = db.begin_nested()
        try:
            block_id = _ensure_master(db, cache, index, block_type_id, item)
            db.execute(
                text("""
                    INSERT INTO spatial.block_boundaries (block_id, period, geom, upload_batch_id)
                    VALUES (:b, :p, CAST(:g AS geometry), :batch)
                    ON CONFLICT (block_id, period) DO UPDATE SET geom = EXCLUDED.geom, upload_batch_id = EXCLUDED.upload_batch_id
                """),
                {"b": block_id, "p": period, "g": to_ewkb(merge_polygons([i.geom for i in entry["items"]])),
                 "batch": str(batch_id)},
            )
            savepoint.commit()
            success += len(entry["features"])
            saved_blocks.add(block_id)
        except Exception as exc:  # satu blok gagal tidak membatalkan blok lain
            savepoint.rollback()
            failed += len(entry["features"])
            last_error = str(exc).splitlines()[0][:500]
            rejected.extend(quarantine.Rejected(no, "GAGAL_DISIMPAN", last_error, f) for no, f in entry["features"])
            # Master yang baru dibuat di savepoint ini ikut batal -> muat ulang cache agar id-nya tidak basi.
            created = cache.created
            index, cache = BlockIndex.load(db), _MasterCache.load(db)
            cache.created = created
    org = _apply_org(db, cache, *_org_plans(db, (i for e in blocks.values() for i in e["items"])))
    progress.stage("karantina")
    quarantined = quarantine.save(db, batch_id, TARGET_TABLE, rejected)
    progress.stage("menyelesaikan")
    org_changed = any(org[k] for k in ("grup_pt_diisi", "grup_pt_diganti", "area_estate_diisi", "area_estate_diganti"))
    stored_version = bump(db, GEOJSON) if success or org_changed else None
    db.commit()

    status = final_status(success, len(features))
    stats = {
        "sukses_master_perusahaan_baru": cache.created["perusahaan"],
        "sukses_master_estate_baru": cache.created["estate"],
        "sukses_master_afdeling_baru": cache.created["afdeling"],
        "sukses_master_blok_baru": cache.created["blok"],
        "blok_pindah_afdeling": cache.created["blok_pindah_afdeling"],
        "dilewati_blok_kembar_di_master": twin_skipped,
        "sukses_geometri_polygon_blok": success,
        "blok_unik_tersimpan": len(saved_blocks),
        "blok_terpecah_digabung": sum(len(e["features"]) > 1 for e in blocks.values()),
        **org,
        "properti_atau_geometri_invalid": invalid,
        "sistem_error_baris": failed,
        "tipe_blok_baru": block_types.created,
        "karantina_count": quarantined,
    }
    finish_batch(db, batch_id, status, success,
                 last_error or (None if status == "SUCCESS" else "Sebagian data tidak valid."), {"detail_statistik": stats})
    return {
        "batch_id": str(batch_id), "total_data_diproses": len(features), "status_proses": status,
        "detail_status": stats, "versi_penyimpanan": stored_version,
    }


def cleanup_period(db: Session, bulan: int, tahun: int, generic_tables: list[tuple[str, str]]) -> dict:
    """Hapus seluruh data spasial berperiode untuk (bulan, tahun). Master tidak disentuh (tidak berperiode di v3)."""
    period = to_period(bulan, tahun)
    tables = [
        ("geometri_polygon_blok", "spatial.block_boundaries"),
        ("geometri_point_tph", "spatial.tph_points"),
        ("geo_jalan", "spatial.roads"),
        ("geo_jembatan", "spatial.bridges"),
        ("geo_landuse", "spatial.landuse_polygons"),
        ("geo_sawit", "spatial.tree_censuses"),
        ("geo_slope", "spatial.slope_polygons"),
        *generic_tables,
    ]
    deleted = {}
    for label, table in tables:
        deleted[label] = db.execute(text(f"DELETE FROM {quote_table(table)} WHERE period = :p"), {"p": period}).rowcount
    stored_version = bump(db, GEOJSON) if any(deleted.values()) else None
    db.commit()
    return {
        "status": "success",
        "periode": period_label(period),
        "detail_terhapus": deleted,
        "versi_penyimpanan": stored_version,
        "catatan": "Master PT/estate/afdeling/blok tidak dihapus karena di gis_db_v3 master tidak berperiode.",
    }
