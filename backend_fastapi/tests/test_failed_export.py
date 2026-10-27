"""Unduhan Excel data gagal (tanpa database)."""
import io
import uuid
from datetime import datetime, timezone

import pytest
from openpyxl import load_workbook

from app.services.upload import failed_export, jobs, part_response
from app.services.upload.failed_export import CELL_LIMIT, TRUNC_NOTE


def _feature(no, **props):
    return {"type": "Feature", "properties": {"OBJECTID": no, **props},
            "geometry": {"type": "Point", "coordinates": [110.0 + no / 1000, 0.5]}}


def _part(part, offset, total, rejected, sources):
    raw = {"status_analisis": "SIAP_DENGAN_CATATAN", "_penolakan": rejected, "_total_fitur": total,
           "_sumber": sources}
    return part_response.build(raw, kategori="blok", bulan=1, tahun=2026, part=part, total_part=2,
                               offset=offset, keep_failed=True)


def _info(results, kind="analyze"):
    jobs_ = [{"kind": kind, "layer": "blok", "filename": "kebun.geojson", "bulan": 1, "tahun": 2026,
              "status": "succeeded", "batch_id": None, "result": r, "part_index": i + 1,
              "finished_at": datetime(2026, 10, 27, 1, 0, tzinfo=timezone.utc)} for i, r in enumerate(results)]
    rows, total = failed_export._analyze_rows(jobs_)
    return {"kind": kind, "layer": "blok", "filename": "kebun.geojson", "bulan": 1, "tahun": 2026,
            "waktu": jobs_[0]["finished_at"], "total": total, "part_total": len(jobs_),
            "rows": sorted(rows, key=failed_export._sort_key)}


def _sheets(content):
    wb = load_workbook(io.BytesIO(content))
    return wb["Data Gagal"], wb["Ringkasan"]


def test_part_response_keeps_failed_sources_and_strips_from_view():
    feats = [_feature(1, Blok="A01"), _feature(2, Blok="A02"), _feature(3, Blok="A03")]
    res = _part(2, 1000, 3, [{"no_preview": 2, "kode": "GEOMETRI_TIDAK_VALID", "alasan": "lihat data #3"}], feats)
    gagal = res[part_response.FAILED_KEY]
    assert gagal == [{"no_preview": 1002, "kode": "GEOMETRI_TIDAK_VALID", "alasan": "lihat data #1003",
                      "sumber": feats[1]}]
    assert part_response.FAILED_KEY not in part_response.strip_private(res)
    # Respons sinkron (tanpa keep_failed) tidak membawa fitur asli
    plain = part_response.build({"_penolakan": [], "_total_fitur": 0, "_sumber": []}, kategori="blok", bulan=1,
                                tahun=2026)
    assert part_response.FAILED_KEY not in plain and "_sumber" not in plain["data"]["ringkasan"]


def test_job_view_hides_failed_sources():
    row = {k: None for k in ("id", "status", "kind", "layer", "bulan", "tahun", "filename", "file_size", "stage",
                             "message", "progress_current", "progress_total", "elapsed", "queue_ahead",
                             "cancel_requested", "error_message", "batch_id", "upload_group_id", "part_index",
                             "part_total", "feature_offset", "created_at", "started_at", "finished_at")}
    row["id"] = uuid.uuid4()
    row["result"] = {"data": {}, "_data_gagal": [{"sumber": {"x": 1}}]}
    assert jobs._view(row, with_result=True)["result"] == {"data": {}}


def test_workbook_contains_all_rows_across_parts_and_summary():
    p1 = _part(1, 0, 2, [{"no_preview": 1, "kode": "ATRIBUT_BLOK_KOSONG", "alasan": "Estate kosong"}],
               [_feature(1, Afdeling="AFD01"), _feature(2)])
    p2 = _part(2, 2, 3, [{"no_preview": 1, "kode": "GEOMETRI_TIDAK_VALID", "alasan": "self-intersection"},
                         {"no_preview": 3, "kode": "BLOK_TIDAK_DITEMUKAN", "alasan": "blok X"}],
               [_feature(3, EstID="E001", Blok="X"), _feature(4), _feature(5, Blok="Z", Extra="ok")])
    info = _info([p1, p2])
    data, summary = _sheets(failed_export.build_workbook(info))
    header = [c.value for c in data[1]]
    assert header[:9] == failed_export.FIXED_HEADERS + ["Estate", "Afdeling", "Blok", "OBJECTID"]
    assert "[file] Extra" in header and header[-1] == "Geometri (WKT)"
    body = [[c.value for c in r] for r in data.iter_rows(min_row=2)]
    assert [r[1] for r in body] == [1, 3, 5]  # nomor data global di file
    assert [r[2] for r in body] == ["ATRIBUT_BLOK_KOSONG", "GEOMETRI_TIDAK_VALID", "BLOK_TIDAK_DITEMUKAN"]
    assert body[1][5:8] == ["E001", None, "X"] and body[0][6] == "AFD01"
    assert body[0][-1].startswith("POINT")
    assert data.freeze_panes == "A2" and data.auto_filter.ref == f"A1:{data.cell(1, len(header)).column_letter}4"
    meta = {r[0].value: r[1].value for r in summary.iter_rows() if r[0].value}
    assert meta["Total Data di File"] == 5 and meta["Total Data Gagal"] == 3
    assert meta["Waktu Proses"] == "27-10-2026 08:00 WIB"
    counts = {r[0].value: r[1].value for r in summary.iter_rows(min_row=12) if r[0].value}
    assert counts == {"ATRIBUT_BLOK_KOSONG": 1, "GEOMETRI_TIDAK_VALID": 1, "BLOK_TIDAK_DITEMUKAN": 1}


@pytest.mark.parametrize("value", ["=HYPERLINK(\"x\")", "+1", "-2+3", "@SUM(A1)", "\t=1"])
def test_formula_injection_is_escaped(value):
    assert failed_export.safe_cell(value) == "'" + value


def test_long_cell_is_truncated_with_note():
    out = failed_export.safe_cell("x" * 40_000)
    assert len(out) == CELL_LIMIT and out.endswith(TRUNC_NOTE)
    assert failed_export.safe_cell(12) == 12 and failed_export.safe_cell(None) is None


def test_old_jobs_without_sources_and_excel_rows():
    old = {"data": {"table_preview": [
        {"no_preview": 1, "status_analisa": "AMAN"},
        {"no_preview": 2, "status_analisa": "GAGAL", "kode_gagal": "NILAI_TIDAK_VALID", "alasan_gagal": "=bad"}]}}
    info = _info([old])
    assert info["total"] == 2 and len(info["rows"]) == 1
    data, _ = _sheets(failed_export.build_workbook(info))
    assert data.cell(2, 5).value == "'=bad"
    # baris Excel transaksi (bukan GeoJSON): tanpa kolom geometri
    info["rows"][0]["sumber"] = {"Blok": "B1", "Luas": float("nan")}
    data, _ = _sheets(failed_export.build_workbook(info))
    assert "Geometri (WKT)" not in [c.value for c in data[1]]


def test_filename_uses_wib_and_clean_name():
    info = {"layer": "blok", "filename": "Kebun A (final)_part1of3.geojson"}
    now = datetime(2026, 10, 27, 0, 5, tzinfo=timezone.utc)
    assert failed_export.export_filename(info, now) == "data_gagal_blok_Kebun_A_final_20261027-0705.xlsx"


def test_endpoint_requires_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).get(f"/api/v1/upload-jobs/{uuid.uuid4()}/data-gagal.xlsx")
    assert r.status_code in (401, 403)


def test_endpoint_returns_xlsx_and_404_when_empty(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app.api.deps import get_current_user, get_db
    from app.main import app
    from app.api.v1.endpoints import upload_jobs as ep

    seen = {}
    p = _part(1, 0, 1, [{"no_preview": 1, "kode": "OBJECTID_GANDA", "alasan": "dobel"}], [_feature(1)])
    info = _info([p])

    def fake_collect(db, job_id, user_id):
        seen["user"] = user_id
        return info
    monkeypatch.setattr(ep.failed_export, "collect", fake_collect)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-1")
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        r = client.get(f"/api/v1/upload-jobs/{uuid.uuid4()}/data-gagal.xlsx")
        assert r.status_code == 200 and seen["user"] == "u-1"
        assert r.headers["content-type"].startswith(ep.XLSX_MEDIA_TYPE)
        assert 'filename="data_gagal_blok_kebun_' in r.headers["content-disposition"]
        assert load_workbook(io.BytesIO(r.content))["Data Gagal"].max_row == 2
        info["rows"] = []
        assert client.get(f"/api/v1/upload-jobs/{uuid.uuid4()}/data-gagal.xlsx").status_code == 404
    finally:
        app.dependency_overrides.clear()
