"""
Mode ganti impor produksi TBS: data lama per (estate, bulan) diganti isi file.

Memakai periode 2099 dan transaksi yang selalu di-rollback, jadi data DB test tidak berubah.
"""
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine
from app.services import trx_import_service as svc
from app.services.trx_import_service import PRODUCTION, ImportScope

JAN, FEB = date(2099, 1, 1), date(2099, 2, 1)


@pytest.fixture()
def db():
    conn = engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        conn.close()


@pytest.fixture()
def blocks(db):
    """Tiga blok dari satu estate: [(kode_estate, kode_afdeling, kode_blok, block_id), ...]."""
    rows = db.execute(text("""
        SELECT es.code, dv.code, bl.code, bl.id FROM master.blocks bl
        JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
        WHERE es.id = (SELECT dv2.estate_id FROM master.blocks b2 JOIN master.divisions dv2 ON dv2.id = b2.division_id
                       GROUP BY dv2.estate_id HAVING count(*) >= 3 ORDER BY dv2.estate_id LIMIT 1)
        ORDER BY bl.id LIMIT 3
    """)).all()
    if len(rows) < 3:
        pytest.skip("Master tidak punya estate dengan minimal 3 blok.")
    return [tuple(r) for r in rows]


def _row(block, year, month, tbs=100.0):
    estate, division, code, _ = block
    row = {"UnitCode": estate, "DivisionCode": division, "KodeBlok": code, "Year": year, "Month": month}
    if tbs is not None:
        row["TbsAktual"] = tbs
    return row


def _import(db, rows, scope=None):
    db.execute(text("DROP TABLE IF EXISTS _stage"))  # tabel staging ON COMMIT DROP tidak ikut hilang di savepoint
    return svc.import_json(db, PRODUCTION, rows, "tes", None, scope)["details"]


def _remaining(db, blocks):
    ids = {b[3]: b[2] for b in blocks}
    found = db.execute(text("SELECT block_id, period FROM trx.block_productions WHERE period = ANY(:p) AND block_id = ANY(:b)"),
                       {"p": [JAN, FEB], "b": list(ids)}).all()
    return sorted((ids[b], p.month) for b, p in found)


def test_replace_is_decided_per_block_and_month(db, blocks):
    a, b, c = blocks
    _import(db, [_row(x, 2099, m) for x in blocks for m in (1, 2)])
    assert len(_remaining(db, blocks)) == 6

    # Januari hanya A, Februari hanya B: A harus hilang dari Februari walau muncul di Januari.
    details = _import(db, [_row(a, 2099, 1), _row(b, 2099, 2)])
    assert details["mode"] == "TIMPA"
    assert details["data_lama_ditemukan"] == 6
    assert details["data_lama_dihapus"] == 4
    assert _remaining(db, blocks) == sorted([(a[2], 1), (b[2], 2)])


def test_scope_parameter_replaces_only_that_estate_and_month(db, blocks):
    a, b, c = blocks
    _import(db, [_row(x, 2099, m) for x in blocks for m in (1, 2)])

    # Baris tanpa Year/Month/UnitCode diisi dari parameter; Februari tidak boleh tersentuh.
    row = {"DivisionCode": c[1], "KodeBlok": c[2], "TbsAktual": 5.0}
    details = _import(db, [row], ImportScope(year=2099, month=1, unit_code=c[0]))
    assert details["mode"] == "TIMPA"
    assert details["parameter"] == {"year": 2099, "month": 1, "unit_code": c[0]}
    assert details["data_lama_dihapus"] == 2
    assert _remaining(db, blocks) == sorted([(c[2], 1), (a[2], 2), (b[2], 2), (c[2], 2)])


def test_scope_rejects_rows_for_other_month(db, blocks):
    a = blocks[0]
    details = _import(db, [_row(a, 2099, 3)], ImportScope(year=2099, month=1, unit_code=a[0]))
    assert details["success_count"] == 0
    assert details["invalid_prop_count"] == 1
    assert details["data_lama_dihapus"] == 0  # tanpa baris valid tidak ada yang dihapus
    assert details["mode"] == "BARU"


def test_rejected_row_keeps_old_data_of_its_block(db, blocks):
    a, b, c = blocks
    _import(db, [_row(x, 2099, 1) for x in blocks])

    # B dikirim dengan nilai negatif (ditolak) -> data lama B dipertahankan; C tidak dikirim -> dihapus.
    details = _import(db, [_row(a, 2099, 1), _row(b, 2099, 1, tbs=-1)])
    assert details["invalid_prop_count"] == 1
    assert details["data_lama_dihapus"] == 1
    assert _remaining(db, blocks) == sorted([(a[2], 1), (b[2], 1)])


def test_new_period_is_mode_baru(db, blocks):
    details = _import(db, [_row(blocks[0], 2099, 1)])
    assert details["mode"] == "BARU"
    assert details["data_lama_ditemukan"] == 0
    assert details["data_lama_dihapus"] == 0


def test_excel_import_is_upsert_only_and_never_deletes(db, blocks):
    import io

    import openpyxl

    _import(db, [_row(x, 2099, 1) for x in blocks])  # lewat JSON: 3 blok untuk Januari

    a = blocks[0]
    sheet = openpyxl.Workbook()
    ws = sheet.active
    ws.append(["Year", "Month", "UnitCode", "DivisionCode", "KodeBlok", "TbsAktual"])
    ws.append([2099, 1, a[0], a[1], a[2], 7.0])  # Excel hanya memuat satu blok
    buffer = io.BytesIO()
    sheet.save(buffer)

    db.execute(text("DROP TABLE IF EXISTS _stage"))
    details = svc.import_productions(db, "tes.xlsx", buffer.getvalue(), None)["details"]
    assert details["success_count"] == 1
    assert details["data_lama_dihapus"] == 0
    assert details["mode"] is None
    assert len(_remaining(db, blocks)) == 3  # dua blok lain tetap ada
