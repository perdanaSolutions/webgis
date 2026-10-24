"""E2E antrian upload Excel transaksi (rotasi): 2 part, header huruf kecil, analyze -> execute, idempoten."""
import io
import uuid

import openpyxl
import pytest
from sqlalchemy import text

from app.db.session import engine
from app.services.upload import jobs
from app.workers import upload_jobs as worker

URL = "/api/v1/upload-jobs"
TAHUN = 2032
HEADER = ["periode", "AREA", "pt", "estate", "afdeling", "BLOK", "luas", "pokok", "rotasi", "pusingan",
          "status pusingan", "bulan", "tanggal"]


def _xlsx(rows) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def empty_queue():
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit.upload_jobs SET status = 'cancelled', finished_at = now() "
                          "WHERE status IN ('queued', 'running')"))
    yield
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM trx.harvest_rotations WHERE extract(year FROM period) = :t"), {"t": TAHUN})


@pytest.fixture()
def blk():
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT es.code AS estate, dv.code AS division, bl.code AS block, bl.id
            FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id ORDER BY bl.id LIMIT 1""")).mappings().first()
    return dict(row)


def _run_group(client, auth, kind, parts, group):
    results = []
    for i, (content, offset) in enumerate(parts, start=1):
        r = client.post(URL, headers=auth, data={
            "kind": kind, "layer": "rotasi-pusingan", "upload_group_id": group, "part_index": i,
            "part_total": len(parts), "feature_offset": offset},
            files={"file": (f"rot.part{i}.xlsx", content, "application/vnd.ms-excel")})
        assert r.status_code == 202, r.text
        assert worker.run_once() == jobs.SUCCEEDED
        results.append(client.get(f"{URL}/{r.json()['job_id']}", headers=auth).json()["result"])
    return results


def _count(block_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM trx.harvest_rotations WHERE block_id = :b "
                                 "AND extract(year FROM period) = :t"), {"b": block_id, "t": TAHUN}).scalar()


def test_rotasi_two_parts_analyze_execute_idempotent(client, auth, blk):
    row = lambda m: [TAHUN, "X", "PT X", blk["estate"], blk["division"], blk["block"], 10.5, 100, 2, 7, "Normal", m, None]
    part1 = _xlsx([row(1), row(2)])
    part2 = _xlsx([row(3), [TAHUN, "", "", blk["estate"], blk["division"], "TIDAKADA999", 1, 1, 1, 1, "", 4, None]])
    parts = [(part1, 0), (part2, 2)]
    group = "grp-1792821442205-3b9da2b7716938"  # ID lama FE (bukan UUID) tetap diterima

    analyzed = _run_group(client, auth, "analyze", parts, group)
    for i, res in enumerate(analyzed, start=1):
        assert {"kategori", "bulan", "tahun", "part", "total_part", "data"} <= set(res)
        assert res["kategori"] == "rotasi-pusingan" and res["part"] == i and res["total_part"] == 2
        assert {"table_preview", "analisa_aman", "analisa_gagal", "ringkasan"} <= set(res["data"])
    nos = [r["no_preview"] for r in analyzed[1]["data"]["table_preview"]]
    assert nos == [3, 4]  # nomor baris di file asli (offset part 2 = 2)
    assert _count(blk["id"]) == 0  # analyze tidak menyimpan

    _run_group(client, auth, "execute", parts, str(uuid.uuid4()))
    assert _count(blk["id"]) == 3
    _run_group(client, auth, "execute", parts, str(uuid.uuid4()))  # unggah ulang: upsert, tidak dobel/terhapus
    assert _count(blk["id"]) == 3
