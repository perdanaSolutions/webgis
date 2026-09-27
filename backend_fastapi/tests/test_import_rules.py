"""Aturan impor Excel yang tidak butuh database."""
from app.services.trx_import_service import keep_last, production_dedupe
from app.utils.parsing import clean_str, is_blank, to_month


def test_blank_markers_from_excel_exports():
    for value in ("(Blanks)", " (blank) ", "-", "N/A", "#N/A", None, float("nan"), "  "):
        assert is_blank(value), value
    assert clean_str("Sedang ") == "Sedang"
    assert clean_str("NA") == "NA"  # bisa jadi kode sah, tidak dianggap kosong


def test_month_names_indonesian_and_english():
    assert [to_month(v) for v in ("Jan", "Mei", "Des", "des", "Agu", "Oct", 11, "03")] == [1, 5, 12, 12, 8, 10, 11, 3]


def _prod(actual, census, bunches=None):
    return {"ffb_actual_kg": actual, "ffb_census_kg": census, "bunches_actual": bunches}


def test_production_prefers_complete_row_over_census_only():
    chosen, _ = production_dedupe([(10, _prod(0, 9000)), (11, _prod(12000, 9000, 600))])
    assert chosen["ffb_actual_kg"] == 12000


def test_production_conflicting_duplicates_are_skipped():
    chosen, reason = production_dedupe([(10, _prod(0, 9870)), (11, _prod(0, 36750))])
    assert chosen is None and "bertentangan" in reason
    chosen, _ = production_dedupe([(10, _prod(100, 1, 5)), (11, _prod(200, 1, 5))])
    assert chosen is None


def test_identical_duplicates_keep_one():
    assert production_dedupe([(1, _prod(5, 5, 1)), (2, _prod(5, 5, 1))])[0] == _prod(5, 5, 1)
    assert keep_last([(1, {"a": 1}), (2, {"a": 2})])[0] == {"a": 2}
