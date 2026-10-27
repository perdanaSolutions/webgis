"""table_preview transaksi (Excel) multi-part: semua baris gagal ber-status GAGAL + gagal_lain (tanpa DB)."""
from app.services.upload import part_response


def test_trx_part_response_marks_every_rejected_row_with_global_numbers():
    first_row = 2  # baris data pertama di Excel (setelah header), sama dengan trx_import_analysis
    excel_nos = [2, 5, 5, 1001]  # nomor baris Excel di part (baris 5 punya dua alasan)
    raw = {"status_analisis": "SIAP_DENGAN_CATATAN", "_total_fitur": 1000, "_penolakan": [
        {"no_preview": n - first_row + 1, "kode": k, "alasan": a}
        for n, k, a in zip(excel_nos, ["NILAI_TIDAK_VALID", "BLOK_TIDAK_DITEMUKAN", "NILAI_TIDAK_VALID", "KODE_BLOK_KOSONG"],
                           ["Luas kosong", "Blok X", "Year kosong", "kosong"])]}
    res = part_response.build(raw, kategori="areal-statement", bulan=1, tahun=2000, part=3, total_part=4, offset=2000)
    preview = res["data"]["table_preview"]
    gagal = [r for r in preview if r["status_analisa"] == "GAGAL"]
    assert [r["no_preview"] for r in gagal] == [2001, 2004, 3000]
    assert gagal[1]["kode_gagal"] == "BLOK_TIDAK_DITEMUKAN"
    assert gagal[1]["gagal_lain"] == [{"kode": "NILAI_TIDAK_VALID", "alasan": "Year kosong"}]
    assert res["data"]["analisa_gagal"]["jumlah_data"] == 3
