"""
Analisis (uji coba) import Excel: laporan rinci, dan tidak ada data yang tersimpan.
Memakai periode 2099 dan nama sintetis supaya tidak bertabrakan dengan data nyata.
"""
import io

import openpyxl
import pytest
from sqlalchemy import text

from app.db.session import engine

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TABLES = ("trx.area_statements", "trx.block_productions", "trx.harvest_rotations", "quarantine.rows",
          "audit.upload_batches", "ref.seed_varieties", "master.areas")


def _xlsx(header, rows) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _snapshot() -> dict:
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in TABLES}


@pytest.fixture()
def block():
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT es.code AS estate, dv.code AS division, bl.code AS block
            FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id ORDER BY bl.id LIMIT 1
        """)).mappings().first()
    if row is None:
        pytest.skip("Master tidak punya blok.")
    return dict(row)


def _analyze(client, auth, url, content):
    return client.post(url, headers=auth, files={"file": ("tes.xlsx", content, XLSX)})


PROD = "/api/v1/pokok-produksi/import-produksi-tbs/analyze"
AREA = "/api/v1/areal-statement/import-excel/analyze"
ROT = "/api/v1/trx-rotasi-pusingan/import-rotasi-pusingan/analyze"
HEADER = ["Year", "Month", "UnitCode", "DivisionCode", "KodeBlok", "TbsAktual"]


def test_production_analysis_explains_each_rejection_and_saves_nothing(client, auth, block):
    e, d, b = block["estate"], block["division"], block["block"]
    content = _xlsx(HEADER, [
        [2099, 1, e, d, b, 10.0],                  # valid
        [2099, 1, "ZZ99", d, b, 10.0],             # estate tidak dikenal
        [2099, 1, e, "AFDZZ99", b, 10.0],          # afdeling tidak ada
        [2099, 1, e, d, "ZZ999", 10.0],            # blok tidak ada di afdeling
        [2099, 1, e, d, b, -5.0],                  # nilai negatif (blok dan periode sama dengan baris valid)
    ])
    before = _snapshot()
    response = _analyze(client, auth, PROD, content)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total_baris"] == 5
    assert data["baris_siap"] == 1
    assert data["data_baru"] == 1
    assert data["baris_ditolak"]["blok_tidak_ditemukan"] == 3
    assert data["baris_ditolak"]["nilai_tidak_valid"] == 1
    assert data["status_analisis"] == "SIAP_DENGAN_CATATAN"
    assert "2099" in data["kesimpulan"]

    rincian = data["rincian"]
    causes = {b["penyebab"] for b in rincian["blok_tidak_ditemukan"]}
    assert causes == {"estate tidak dikenal di master", "afdeling tidak ada di estate ini", "blok tidak ada di afdeling ini"}
    assert {r["no_baris"] for r in rincian["data_ditolak"]} == {3, 4, 5, 6}
    assert rincian["per_periode"] == [{"periode": "1-2099", "jumlah_data": 1}]
    assert rincian["per_estate"][0]["estate"] == e
    assert any(w["kode"] == "TIDAK_MENGHAPUS" for w in data["peringatan"])

    assert _snapshot() == before  # tidak ada yang tersimpan: data, karantina, maupun riwayat upload


def test_analysis_matches_real_import_numbers(client, auth, block):
    """Angka analisis harus sama dengan hasil import sungguhan (import dibatalkan lewat penghapusan data uji)."""
    e, d, b = block["estate"], block["division"], block["block"]
    content = _xlsx(HEADER, [[2099, 2, e, d, b, 10.0], [2099, 2, "ZZ99", d, b, 10.0]])
    analysis = _analyze(client, auth, PROD, content).json()
    try:
        real = client.post("/api/v1/pokok-produksi/import-produksi-tbs", headers=auth,
                           files={"file": ("tes.xlsx", content, XLSX)}).json()["details"]
        assert analysis["baris_siap"] == real["success_count"]
        assert analysis["data_baru"] == real["data_baru"]
        assert analysis["baris_ditolak"]["total"] == real["karantina_count"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM trx.block_productions WHERE period = '2099-02-01'"))
            conn.execute(text("DELETE FROM quarantine.rows WHERE (data->>'Year')::int = 2099"))


def test_missing_required_columns_are_reported(client, auth):
    content = _xlsx(["Tahun", "Bulan", "Blokk", "TbsAktual"], [[2099, 1, "A001", 1.0]])  # 'Blokk' salah ketik
    data = _analyze(client, auth, PROD, content).json()
    warning = next(w for w in data["peringatan"] if w["kode"] == "KOLOM_WAJIB_TIDAK_ADA")
    assert "Kode blok" in warning["pesan"]
    assert data["status_analisis"] == "TIDAK_ADA_DATA_VALID"
    assert "Blokk" in data["rincian"]["kolom_tidak_dibaca"]


def test_area_statement_analysis_lists_new_reference_values_without_creating_them(client, auth, block):
    e, d, b = block["estate"], block["division"], block["block"]
    with engine.connect() as conn:
        area = conn.execute(text("SELECT code FROM master.areas ORDER BY id LIMIT 1")).scalar()
        status = conn.execute(text("SELECT code FROM ref.planting_statuses ORDER BY id LIMIT 1")).scalar()
    if not area or not status:
        pytest.skip("Master area / status tanam kosong.")
    header = ["Year", "Month", "AreaCode", "UnitCode", "DivisionCode", "KodeBlok", "StatusTanam", "JenisBibit", "LuasTanam"]
    content = _xlsx(header, [
        [2099, 1, area, e, d, b, status, "BibitUjiXYZ", 10.0],   # bibit baru -> dibuat otomatis saat import
        [2099, 1, area, e, d, b, None, "Socfin", 10.0],          # StatusTanam kosong
    ])
    before = _snapshot()
    data = _analyze(client, auth, AREA, content).json()
    assert data["baris_ditolak"]["nilai_tidak_valid"] == 1
    assert "BibitUjiXYZ" in str(data["rincian"]["nilai_referensi_baru"])
    assert any(w["kode"] == "NILAI_REFERENSI_BARU" for w in data["peringatan"])
    assert _snapshot() == before  # nilai referensi baru tidak benar-benar dibuat


def test_rotation_analysis_and_login_required(client, auth, block):
    content = _xlsx(["Periode", "Bulan", "Estate", "Afdeling", "Blok", "Luas", "Pokok", "Rotasi", "Pusingan"],
                    [[2099, 1, block["estate"], block["division"], block["block"], 10, 100, 3, 4]])
    data = _analyze(client, auth, ROT, content).json()
    assert data["baris_siap"] == 1
    assert client.post(ROT, files={"file": ("tes.xlsx", content, XLSX)}).status_code == 401
