"""
Koreksi manual atribut master struktur v2: grup PT (companies.group_id) dan area saat ini estate
(estates.area_id). Sumber utamanya tetap upload GeoJSON blok; endpoint ini untuk perbaikan satu per satu.
Hanya grup/area yang sudah terdaftar yang bisa dipilih (dicocokkan lewat kode atau nama).
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.services.data_version import GEOJSON, HISTORY, bump
from app.services.user_activity import record_user_activity


def _find(db: Session, table: str, ref: str, label: str, field: str) -> dict:
    """Baris master lewat id, kode, atau nama (tanpa membedakan huruf besar/kecil)."""
    row = db.execute(text(f"""
        SELECT id, code, name FROM {table}
        WHERE id::text = :r OR upper(code) = upper(:r) OR upper(name) = upper(:r)
        ORDER BY (id::text = :r) DESC, (upper(code) = upper(:r)) DESC LIMIT 1
    """), {"r": (ref or "").strip()}).mappings().first()
    if row is None:
        if field == "path":
            raise not_found(f"{label} '{ref}' tidak ditemukan.")
        raise bad_request(f"{label} '{ref}' belum terdaftar. Pilih dari daftar yang ada.", field=field)
    return dict(row)


def _save(db: Session, user, action: str, resource: str, record_id: int, detail: dict) -> None:
    record_user_activity(db, user, action, resource, record_id=str(record_id), detail=detail)
    bump(db, GEOJSON)   # properti kode_grup/kode_area di peta
    bump(db, HISTORY)   # filter histori memakai grup/area master
    db.commit()


def set_company_group(db: Session, user, company_ref: str, group_ref: str) -> dict:
    company = _find(db, "master.companies", company_ref, "PT", "path")
    group = _find(db, "master.groups", group_ref, "Grup", "kode_grup")
    before = db.execute(text("SELECT gr.code FROM master.companies co LEFT JOIN master.groups gr ON gr.id = co.group_id "
                             "WHERE co.id = :c"), {"c": company["id"]}).scalar()
    if before != group["code"]:
        db.execute(text("UPDATE master.companies SET group_id = :g WHERE id = :c"),
                   {"g": group["id"], "c": company["id"]})
        _save(db, user, "UPDATE_COMPANY_GROUP", "master.companies", company["id"],
              {"kode_pt": company["code"], "grup_sebelum": before, "grup_sesudah": group["code"]})
    return {"kode_pt": company["code"], "nama_pt": company["name"], "kode_grup": group["code"],
            "grup_sebelum": before, "diubah": before != group["code"]}


def set_estate_area(db: Session, user, estate_ref: str, area_ref: str) -> dict:
    estate = _find(db, "master.estates", estate_ref, "Estate", "path")
    area = _find(db, "master.areas", area_ref, "Area", "kode_area")
    before = db.execute(text("SELECT ar.code FROM master.estates es LEFT JOIN master.areas ar ON ar.id = es.area_id "
                             "WHERE es.id = :e"), {"e": estate["id"]}).scalar()
    if before != area["code"]:
        db.execute(text("UPDATE master.estates SET area_id = :a WHERE id = :e"), {"a": area["id"], "e": estate["id"]})
        _save(db, user, "UPDATE_ESTATE_AREA", "master.estates", estate["id"],
              {"kode_est": estate["code"], "area_sebelum": before, "area_sesudah": area["code"]})
    return {"kode_est": estate["code"], "nama_estate": estate["name"], "kode_area": area["code"],
            "area_sebelum": before, "diubah": before != area["code"]}
