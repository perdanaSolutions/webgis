from app.services.upload import context, part_response


def _result():
    return {
        "status_analisis": "SIAP_DENGAN_CATATAN", "kesimpulan": "x", "total_data_landuse": 4,
        "peringatan": [
            {"kode": "BLOK_TIDAK_DITEMUKAN", "level": "PERINGATAN", "jumlah": 1, "pesan": "a"},
            {"kode": "MENGGANTI_DATA_LAMA", "level": "INFO", "jumlah": 3, "pesan": "b"},
        ],
        "rincian": {
            "per_estate": [{"estate": "E1", "data_siap": 2}],
            "data_ditolak": [{"no_preview": 2, "kode": "BLOK_TIDAK_DITEMUKAN", "alasan": "Blok X"}],
            "blok_terpecah": [{"blok": "E1/A/1", "no_preview": [1, 3]}],
        },
        "_penolakan": [
            {"no_preview": 2, "kode": "BLOK_TIDAK_DITEMUKAN", "alasan": "Blok X"},
            {"no_preview": 4, "kode": "GEOMETRI_TIDAK_VALID", "alasan": "kosong"},
        ],
        "_total_fitur": 4,
    }


def test_build_uses_global_no_preview_and_splits_aman_gagal():
    out = part_response.build(_result(), kategori="landuse", bulan=1, tahun=2026, part=2, total_part=3, offset=1000)
    assert {k: out[k] for k in ("kategori", "bulan", "tahun", "part", "total_part")} == {
        "kategori": "landuse", "bulan": 1, "tahun": 2026, "part": 2, "total_part": 3}
    data = out["data"]
    assert [r["no_preview"] for r in data["table_preview"]] == [1001, 1002, 1003, 1004]
    assert [r["status_analisa"] for r in data["table_preview"]] == ["AMAN", "GAGAL", "AMAN", "GAGAL"]
    assert data["table_preview"][1]["kode_gagal"] == "BLOK_TIDAK_DITEMUKAN"
    assert data["table_preview"][0]["alasan_gagal"] is None
    assert data["analisa_aman"]["jumlah_data"] == 2
    assert data["analisa_aman"]["rincian"]["blok_terpecah"][0]["no_preview"] == [1001, 1003]
    assert [w["kode"] for w in data["analisa_aman"]["catatan"]] == ["MENGGANTI_DATA_LAMA"]
    assert data["analisa_gagal"]["jumlah_data"] == 2
    assert data["analisa_gagal"]["rincian"]["data_ditolak"][0]["no_preview"] == 1002
    assert {g["kode"] for g in data["analisa_gagal"]["per_kode"]} == {"BLOK_TIDAK_DITEMUKAN", "GEOMETRI_TIDAK_VALID"}
    assert data["ringkasan"]["status_analisis"] == "SIAP_DENGAN_CATATAN"
    assert data["ringkasan"]["no_preview_awal"] == 1001 and data["ringkasan"]["no_preview_akhir"] == 1004
    assert "_penolakan" not in data["ringkasan"]


def test_single_upload_defaults():
    out = part_response.build({"_total_fitur": 2}, kategori="tph", bulan=5, tahun=2026)
    assert out["part"] == 1 and out["total_part"] == 1
    assert [r["no_preview"] for r in out["data"]["table_preview"]] == [1, 2]


def test_part_context_is_scoped():
    assert context.current().offset == 0
    with context.use(context.PartContext(offset=2000, protected_batch_ids=("a",))):
        assert context.current().offset == 2000
        assert context.protected_params() == {"protected_batches": ["a"]}
    assert context.current().offset == 0 and context.protected_params() == {"protected_batches": []}
