"""Perbaikan 30 Okt 2026: gap 0 = OPTIMUM, None = tanpa kategori, ringkasan GAP Year to Date."""
from datetime import date

from app.services.block_detail_service import gap_kategori, gap_value
from app.services.history_service import _production_gap_summary


def test_gap_nol_optimum_dan_none_tanpa_kategori():
    assert gap_value(1.2, 1.2) == 0.0
    assert gap_kategori(0.0) == "OPTIMUM"
    assert gap_kategori(gap_value(1.2, 1.2)) == "OPTIMUM"
    assert gap_kategori(5) == "OPTIMUM"
    assert gap_kategori(-0.01) == "GAP I"
    assert gap_kategori(-25) == "GAP II"
    assert gap_kategori(-41) == "GAP III"
    assert gap_value(1.0, 0) is None and gap_value(0, None) is None
    assert gap_kategori(None) == ""


class _Res:
    def __init__(self, rows):
        self.rows = rows

    def scalar(self):
        return self.rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, latest, rows):
        self.calls = []
        self.queue = [latest, rows]

    def execute(self, stmt, params):
        self.calls.append((str(stmt), params))
        return _Res(self.queue.pop(0))


def test_gap_summary_ytd_agregat_januari_sd_periode():
    rows = [
        {"act": 1000.0, "tgt": 1000.0, "luas": 10.0},   # gap 0 -> OPTIMUM
        {"act": 700.0, "tgt": 1000.0, "luas": 5.5},     # -30 -> GAP II
        {"act": 0.0, "tgt": None, "luas": 3.0},         # tanpa target -> tidak dihitung
    ]
    db = _Db(date(2026, 8, 1), rows)
    out = _production_gap_summary(db, "SELECT 1", {"gap_as_of": date(2026, 8, 1), "gap_ytd": True}, "", "budget")
    sql, params = db.calls[1]
    assert "BETWEEN :start AND :latest" in sql and params["start"] == date(2026, 1, 1)
    assert out["year_to_date"] is True
    assert out["periode_mulai"] == {"tahun": 2026, "bulan": 1}
    assert out["periode"] == {"tahun": 2026, "bulan": 8}
    kat = {k["kategori"]: k for k in out["kategori"]}
    assert kat["OPTIMUM"]["jumlah_blok"] == 1 and kat["OPTIMUM"]["luas"] == 10.0
    assert kat["GAP II"]["jumlah_blok"] == 1 and kat["GAP II"]["luas"] == 5.5
    assert out["grand_total"]["jumlah_blok"] == 2


def test_gap_summary_non_ytd_periode_tunggal():
    db = _Db(date(2026, 8, 1), [{"act": 1.0, "tgt": 1.0, "luas": 2.0}])
    out = _production_gap_summary(db, "SELECT 1", {"gap_as_of": None}, "", "budget")
    assert out["year_to_date"] is False and out["periode_mulai"] == out["periode"]
    assert out["kategori"][0]["kategori"] == "OPTIMUM"


def test_batas_excel_lama_satu_aturan():
    from app.services.history_service import gap_category
    from app.utils.gap import gap_kategori as rule
    cases = {0.0: "OPTIMUM", 0.5: "OPTIMUM", -0.0001: "GAP I", -19.9999: "GAP I", -20.0: "GAP II",
             -30: "GAP II", -40.0: "GAP II", -40.0001: "GAP III", -100: "GAP III"}
    for value, expected in cases.items():
        assert rule(value) == expected, value
        assert gap_kategori(value) == expected, value
        assert gap_category(value) == expected, value
    assert gap_category(None) is None
