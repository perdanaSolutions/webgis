"""Export Excel data transaksi: header sama dengan template import, filter periode/estate, dan bisa dibaca ulang."""
import io

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from app.db.session import engine
from app.services import trx_export_service as svc
from app.utils.excel import read_excel_rows

ENDPOINTS = {
    "areal-statement": "/api/v1/areal-statement/export-excel",
    "produksi-tbs": "/api/v1/pokok-produksi/export-excel",
    "rotasi-pusingan": "/api/v1/trx-rotasi-pusingan/export-excel",
}


def _latest(table: str):
    with engine.connect() as conn:
        return conn.execute(text(f"""
            SELECT extract(year FROM t.period)::int AS y, extract(month FROM t.period)::int AS m, es.code AS est,
                   count(*) OVER (PARTITION BY t.period, es.id) AS n
            FROM {table} t JOIN master.blocks bl ON bl.id = t.block_id
            JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            ORDER BY t.period DESC, es.code LIMIT 1
        """)).mappings().first()


@pytest.mark.parametrize("slug", list(ENDPOINTS))
def test_export_header_dan_filter(client, auth, slug):
    kind = svc.EXPORT_KINDS[slug]
    sample = _latest(kind.table)
    if sample is None:
        pytest.skip(f"{kind.table} kosong di database test.")
    res = client.get(ENDPOINTS[slug], headers=auth,
                     params={"tahun": sample["y"], "bulan": sample["m"], "kode_est": sample["est"]})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith(svc.XLSX_MEDIA_TYPE)
    assert "attachment" in res.headers["content-disposition"]

    wb = load_workbook(io.BytesIO(res.content), read_only=True)
    assert wb.sheetnames == ["Data", "Info"]
    rows = list(wb["Data"].iter_rows(values_only=True))
    assert tuple(rows[0]) == kind.headers
    assert len(rows) - 1 == sample["n"]

    # File bisa dibaca lagi oleh pembaca import (sheet pertama) dengan header yang sama.
    parsed = read_excel_rows("export.xlsx", res.content)
    assert len(parsed) == sample["n"]
    assert list(parsed[0].keys()) == list(kind.headers)
    year_col = "Periode" if slug == "rotasi-pusingan" else "Year"
    assert {int(r[year_col]) for r in parsed} == {sample["y"]}


def test_bulan_tanpa_tahun_ditolak(client, auth):
    res = client.get(ENDPOINTS["areal-statement"], headers=auth, params={"bulan": 1})
    assert res.status_code == 400


def test_periode_kosong_hanya_header(client, auth):
    res = client.get(ENDPOINTS["produksi-tbs"], headers=auth, params={"tahun": 2099, "bulan": 12})
    assert res.status_code == 200
    rows = list(load_workbook(io.BytesIO(res.content), read_only=True)["Data"].iter_rows(values_only=True))
    assert len(rows) == 1


def test_tanpa_login_ditolak(client):
    assert client.get(ENDPOINTS["areal-statement"]).status_code == 401


@pytest.mark.parametrize("slug", list(ENDPOINTS))
def test_export_bisa_diimpor_ulang_tanpa_perubahan(client, auth, slug):
    """Analisa import atas file hasil export: semua baris siap dan tidak ada nilai yang berubah."""
    from sqlalchemy.orm import Session

    from app.services import trx_import_analysis
    from app.services.trx_import_service import AREA_STATEMENT, PRODUCTION, ROTATION

    kind = svc.EXPORT_KINDS[slug]
    sample = _latest(kind.table)
    if sample is None:
        pytest.skip(f"{kind.table} kosong di database test.")
    res = client.get(ENDPOINTS[slug], headers=auth,
                     params={"tahun": sample["y"], "bulan": sample["m"], "kode_est": sample["est"]})
    trx_kind = {"areal-statement": AREA_STATEMENT, "produksi-tbs": PRODUCTION, "rotasi-pusingan": ROTATION}[slug]
    with Session(engine) as db:
        report = trx_import_analysis.analyze_excel(db, trx_kind, "export.xlsx", res.content)
    assert report.get("data_tidak_berubah") == sample["n"], {k: report.get(k) for k in (
        "status_analisis", "baris_siap", "data_baru", "data_diperbarui", "data_tidak_berubah", "baris_ditolak")}
