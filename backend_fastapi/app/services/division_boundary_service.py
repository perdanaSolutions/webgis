"""
Batas afdeling per periode (spatial.division_boundaries, source = 'derived').

Batas afdeling periode P = union batas blok afdeling itu dengan semantik "kondisi per periode" yang sama
dengan GeoJSON blok: tiap blok memakai batas TERBARU dengan period <= P. Baris derived hanya dibuat untuk
periode yang benar-benar punya upload batas blok di afdeling itu (mengikuti riwayat upload blok).

Pembersihan (dalam meter, di proyeksi UTM zona centroid afdeling):
- celah/overlap tipis antar blok ditutup: buffer +GAP_M lalu -GAP_M (join mitre, sudut tetap tajam);
- lubang dengan luas < HOLE_MIN_M2 dibuang (lubang besar = enclave asli, dipertahankan);
- geom_display = ST_SimplifyPreserveTopology(DISPLAY_TOLERANCE_M) untuk tampilan peta.
Nilai ambang di-tuning dari data db_uat_v1 (28-10-2026): 1.182 lubang < 0,5 m2 (celah antar blok),
lubang asli terkecil 10.817 m2.

Union GEOS bisa gagal (TopologyException). Tiap pasangan (afdeling, periode) dicoba berurutan:
makevalid -> buffer0 -> grid (snap 1e-7 derajat); semua error dicatat lengkap di laporan.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.data_version import GEOJSON, bump

logger = logging.getLogger(__name__)

GAP_M = 1.0
HOLE_MIN_M2 = 1000.0
DISPLAY_TOLERANCE_M = 1.0
SOURCE_DERIVED = "derived"
TABLE = "spatial.division_boundaries"

# Ekspresi per potongan blok sebelum union, urut dari yang paling setia ke yang paling toleran.
_PIECE = {
    "makevalid": "ST_MakeValid(s.geom)",
    "buffer0": "ST_Buffer(ST_MakeValid(s.geom), 0)",
    "grid": "ST_Buffer(ST_SnapToGrid(ST_MakeValid(s.geom), 0.0000001), 0)",
}
_UNION = {
    "makevalid": "ST_UnaryUnion(ST_Collect({piece}))",
    "buffer0": "ST_Buffer(ST_Union({piece}), 0)",
    "grid": "ST_UnaryUnion(ST_Collect({piece}), 0.0000001)",
}
MODES = tuple(_PIECE)


def _compute_sql(mode: str) -> str:
    union = _UNION[mode].format(piece=_PIECE[mode])
    return f"""
        WITH src AS (
            SELECT b.geom
            FROM master.blocks bl
            JOIN LATERAL (
                SELECT bb.geom FROM spatial.block_boundaries bb
                WHERE bb.block_id = bl.id AND bb.period <= :period
                ORDER BY bb.period DESC LIMIT 1
            ) b ON true
            WHERE bl.division_id = :division_id
        ),
        u AS (
            SELECT count(*) AS n_blok, ST_CollectionExtract(ST_MakeValid({union}), 3) AS g
            FROM src s
        ),
        z AS (
            SELECT n_blok, g,
                   CASE WHEN ST_Y(ST_Centroid(g)) >= 0 THEN 32600 ELSE 32700 END
                   + LEAST(60, GREATEST(1, floor((ST_X(ST_Centroid(g)) + 180) / 6)::int + 1)) AS srid
            FROM u WHERE n_blok > 0 AND NOT ST_IsEmpty(g)
        ),
        closed AS (
            SELECT n_blok, srid,
                   ST_CollectionExtract(ST_MakeValid(ST_Buffer(ST_Buffer(ST_Transform(g, srid), :gap, 'join=mitre mitre_limit=2'),
                                                              -:gap, 'join=mitre mitre_limit=2')), 3) AS m
            FROM z
        ),
        noholes AS (
            SELECT c.n_blok, c.srid, ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Collect(
                ST_MakePolygon(ST_ExteriorRing(d.geom), ARRAY(
                    SELECT ST_ExteriorRing(r.geom) FROM ST_DumpRings(d.geom) r
                    WHERE r.path[1] > 0 AND ST_Area(r.geom) >= :hole_min))
            )), 3)) AS m
            FROM closed c, ST_Dump(c.m) d
            WHERE ST_GeometryType(d.geom) = 'ST_Polygon'
            GROUP BY c.n_blok, c.srid
        )
        SELECT n_blok,
               ST_AsEWKB(ST_Multi(ST_Transform(m, 4326))) AS geom,
               ST_AsEWKB(ST_Multi(ST_CollectionExtract(ST_MakeValid(
                   ST_Transform(ST_SimplifyPreserveTopology(m, :display_tol), 4326)), 3))) AS geom_display,
               ST_Area(m) / 10000.0 AS luas_ha,
               (SELECT count(*) FROM ST_Dump(m) d, ST_DumpRings(d.geom) r WHERE r.path[1] > 0) AS holes,
               ST_NumGeometries(m) AS parts
        FROM noholes
    """


_UPSERT = f"""
    INSERT INTO {TABLE} (division_id, estate_id, period, geom, geom_display, n_blok, luas_ha, source, updated_at)
    SELECT :division_id, dv.estate_id, :period, ST_GeomFromEWKB(:geom), ST_GeomFromEWKB(:geom_display),
           :n_blok, round(CAST(:luas_ha AS numeric), 4), '{SOURCE_DERIVED}', now()
    FROM master.divisions dv WHERE dv.id = :division_id
    ON CONFLICT (division_id, period, source) DO UPDATE SET
        estate_id = EXCLUDED.estate_id, geom = EXCLUDED.geom, geom_display = EXCLUDED.geom_display,
        n_blok = EXCLUDED.n_blok, luas_ha = EXCLUDED.luas_ha, updated_at = now()
"""


@dataclass
class RefreshReport:
    dihitung: int = 0
    dihapus_basi: int = 0
    gagal: int = 0
    fallback: dict[str, int] = field(default_factory=dict)
    lubang: int = 0
    multipart: int = 0
    errors: list[dict] = field(default_factory=list)
    detik: float = 0.0

    def as_dict(self) -> dict:
        return {"afdeling_periode_dihitung": self.dihitung, "baris_basi_dihapus": self.dihapus_basi,
                "gagal": self.gagal, "fallback": self.fallback, "lubang_tersisa": self.lubang,
                "afdeling_multipart": self.multipart, "errors": self.errors, "detik": round(self.detik, 2)}


def table_exists(db: Session) -> bool:
    return db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": TABLE}).scalar()


def compute(db: Session, division_id: int, period: date) -> tuple[dict | None, str, list[str]]:
    """(hasil | None bila tidak ada blok, mode yang berhasil, error per mode yang gagal)."""
    errors: list[str] = []
    params = {"division_id": division_id, "period": period, "gap": GAP_M, "hole_min": HOLE_MIN_M2,
              "display_tol": DISPLAY_TOLERANCE_M}
    for mode in MODES:
        savepoint = db.begin_nested()
        try:
            row = db.execute(text(_compute_sql(mode)), params).mappings().first()
            savepoint.commit()
            return (dict(row) if row else None), mode, errors
        except Exception as exc:  # GEOS TopologyException dkk: coba mode berikutnya
            savepoint.rollback()
            errors.append(f"{mode}: {str(exc).splitlines()[0][:400]}")
    raise RuntimeError(f"Union batas afdeling id={division_id} periode {period:%Y-%m} gagal di semua mode: "
                       + " | ".join(errors))


def target_periods(db: Session, division_id: int, from_period: date | None) -> tuple[list[date], set[date]]:
    """(periode yang punya upload batas blok, periode baris derived yang sudah tersimpan)."""
    flt = "AND bb.period >= :fp" if from_period else ""
    blok = db.execute(text(f"""
        SELECT DISTINCT bb.period FROM spatial.block_boundaries bb
        JOIN master.blocks bl ON bl.id = bb.block_id
        WHERE bl.division_id = :d {flt} ORDER BY 1
    """), {"d": division_id, "fp": from_period}).scalars().all()
    flt2 = "AND period >= :fp" if from_period else ""
    stored = set(db.execute(text(f"SELECT period FROM {TABLE} WHERE division_id = :d AND source = '{SOURCE_DERIVED}' {flt2}"),
                            {"d": division_id, "fp": from_period}).scalars().all())
    return list(blok), stored


def refresh_divisions(db: Session, division_ids, from_period: date | None = None, *, periods: list[date] | None = None,
                      bump_version: bool = True) -> RefreshReport:
    """Hitung ulang baris derived. Tidak commit; pemanggil yang commit/rollback."""
    started = time.monotonic()
    report = RefreshReport()
    for division_id in sorted(set(division_ids)):
        blok_periods, stored = target_periods(db, division_id, from_period)
        if periods is not None:
            blok_periods = [p for p in blok_periods if p in periods]
            stored = {p for p in stored if p in periods}
        for period in blok_periods:
            try:
                row, mode, errors = compute(db, division_id, period)
            except Exception as exc:
                report.gagal += 1
                report.errors.append({"division_id": division_id, "periode": f"{period:%Y-%m}", "error": str(exc)})
                logger.error("Batas afdeling gagal dihitung: %s", exc)
                continue
            if mode != MODES[0]:
                report.fallback[mode] = report.fallback.get(mode, 0) + 1
                logger.warning("Batas afdeling id=%s %s memakai fallback %s (%s)", division_id, period, mode, errors)
            if row is None:
                continue
            db.execute(text(_UPSERT), {"division_id": division_id, "period": period, "geom": bytes(row["geom"]),
                                       "geom_display": bytes(row["geom_display"]), "n_blok": row["n_blok"],
                                       "luas_ha": row["luas_ha"]})
            report.dihitung += 1
            report.lubang += int(row["holes"] or 0)
            report.multipart += int((row["parts"] or 0) > 1)
        stale = sorted(stored - set(blok_periods))
        if stale:  # periode batas blok afdeling ini sudah dihapus (cleanup periode) -> baris derived ikut dibuang
            report.dihapus_basi += db.execute(
                text(f"DELETE FROM {TABLE} WHERE division_id = :d AND source = '{SOURCE_DERIVED}' AND period = ANY(:ps)"),
                {"d": division_id, "ps": stale}).rowcount
    if bump_version and (report.dihitung or report.dihapus_basi):
        bump(db, GEOJSON)  # cache Redis GET /spatial/* (termasuk /spatial/afdeling/geojson) jadi basi
    report.detik = time.monotonic() - started
    return report


def divisions_for(db: Session, *, block_ids=None, estate: str | None = None, period: date | None = None,
                  all_divisions: bool = False) -> list[int]:
    """Afdeling yang perlu dihitung. block_ids -> SEMUA afdeling di estate blok tsb (blok bisa pindah afdeling)."""
    if block_ids is not None:
        return db.execute(text("""
            SELECT dv.id FROM master.divisions dv WHERE dv.estate_id IN (
                SELECT d2.estate_id FROM master.blocks bl JOIN master.divisions d2 ON d2.id = bl.division_id
                WHERE bl.id = ANY(:ids))
        """), {"ids": list(block_ids)}).scalars().all()
    clauses, params = [], {}
    if estate:
        clauses.append("(upper(es.code) = upper(:est) OR upper(es.short_name) = upper(:est) OR es.id::text = :est)")
        params["est"] = estate
    if period:
        clauses.append("EXISTS (SELECT 1 FROM master.blocks bl JOIN spatial.block_boundaries bb ON bb.block_id = bl.id "
                       "WHERE bl.division_id = dv.id AND bb.period = :p)")
        params["p"] = period
    if not clauses and not all_divisions:
        return []
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return db.execute(text(f"SELECT dv.id FROM master.divisions dv JOIN master.estates es ON es.id = dv.estate_id "
                           f"{where} ORDER BY dv.id"), params).scalars().all()


def refresh_after_block_change(bind, *, block_ids=None, period: date, all_in_period: bool = False) -> dict:
    """
    Hook setelah data batas blok SUDAH di-commit. Sesi terpisah: kegagalan di sini tidak pernah membatalkan
    data blok; error dicatat (log + laporan) dengan alasan lengkap.
    """
    try:
        with Session(bind=bind) as s:
            if not table_exists(s):
                return {"status": "dilewati", "alasan": f"Tabel {TABLE} belum ada (migrasi 021 belum dijalankan)."}
            if all_in_period:
                divisions = s.execute(text(f"SELECT DISTINCT division_id FROM {TABLE} WHERE period = :p "
                                           "UNION SELECT bl.division_id FROM spatial.block_boundaries bb "
                                           "JOIN master.blocks bl ON bl.id = bb.block_id WHERE bb.period = :p"),
                                      {"p": period}).scalars().all()
            else:
                divisions = divisions_for(s, block_ids=block_ids or [])
            if not divisions:
                return {"status": "dilewati", "alasan": "Tidak ada afdeling terdampak."}
            report = refresh_divisions(s, divisions, from_period=period)
            s.commit()
            out = {"status": "gagal_sebagian" if report.gagal else "sukses", "afdeling": len(divisions), **report.as_dict()}
            if report.gagal:
                logger.error("Refresh batas afdeling sebagian gagal: %s", report.errors)
            return out
    except Exception as exc:
        logger.exception("Refresh batas afdeling gagal (data blok tetap tersimpan): %s", exc)
        return {"status": "gagal", "alasan": f"Batas afdeling tidak diperbarui: {str(exc).splitlines()[0][:500]}. "
                                              "Data batas blok tetap tersimpan; jalankan "
                                              "`python -m scripts.backfill_division_boundaries --period YYYY-MM`."}


# ------------------------------------------------------------------ baca (endpoint)
def afdeling_geojson(db: Session, flt, bulan: int | None, tahun: int | None) -> dict:
    """Batas afdeling terbaru dengan period <= periode diminta (semantik sama dengan GeoJSON blok).
    Lingkup: afdeling yang punya minimal satu blok dalam filter + hak akses user."""
    from app.utils.period import as_of_period, period_label

    as_of = as_of_period(bulan, tahun)
    sub, params = flt.block_ids_subquery()
    params["as_of"] = as_of
    period_filter = "AND db.period <= :as_of" if as_of else ""
    rows = db.execute(text(f"""
        SELECT dv.id AS division_id, dv.code AS kode_afd, es.code AS kode_est, es.short_name AS estate_short_name,
               es.name AS nama_estate, co.code AS kode_pt, b.period, b.n_blok, b.luas_ha, b.source,
               ST_AsGeoJSON(COALESCE(b.geom_display, b.geom), 6) AS geom_json
        FROM master.divisions dv
        JOIN master.estates es ON es.id = dv.estate_id
        JOIN master.companies co ON co.id = es.company_id
        JOIN LATERAL (
            SELECT db.period, db.n_blok, db.luas_ha, db.source, db.geom, db.geom_display
            FROM {TABLE} db
            WHERE db.division_id = dv.id {period_filter}
            ORDER BY db.period DESC, (db.source = 'official') DESC LIMIT 1
        ) b ON true
        WHERE dv.id IN (SELECT bl.division_id FROM master.blocks bl WHERE bl.id IN ({sub}))
        ORDER BY es.code, dv.code
    """), params).mappings().all()
    import json

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geom_json"]),
            "properties": {
                "division_id": str(r["division_id"]), "kode_afd": r["kode_afd"], "kode_est": r["kode_est"],
                "estate_short_name": r["estate_short_name"] or r["kode_est"], "nama_estate": r["nama_estate"],
                "kode_pt": r["kode_pt"], "n_blok": r["n_blok"],
                "luas_ha": float(r["luas_ha"]) if r["luas_ha"] is not None else None,
                "sumber": r["source"], "periode_batas": period_label(r["period"]),
                "bulan": r["period"].month, "tahun": r["period"].year,
            },
        })
    return {"type": "FeatureCollection", "features": features}
