"""Upload transaksi lewat antrian hanya menerima file Excel (.xlsx/.xls). Tanpa DB."""
import pytest

from app.core.exceptions import AppError
from app.services.upload.trx_file_rules import ensure_trx_excel_file, is_trx_excel_filename


@pytest.mark.parametrize("name", ["data.xlsx", "DATA.XLS", " rotasi.part1of2.xlsx "])
def test_excel_diterima(name):
    assert is_trx_excel_filename(name)
    ensure_trx_excel_file(name)


@pytest.mark.parametrize("name", ["data.json", "data.geojson", "data.csv", "data.xlsx.json", "", None])
def test_non_excel_ditolak_400(name):
    assert not is_trx_excel_filename(name)
    with pytest.raises(AppError) as info:
        ensure_trx_excel_file(name)
    assert info.value.status_code == 400
    err = info.value.detail["errors"][0]
    assert err["field"] == "file"
    assert ".xlsx" in err["msg"] and "JSON" in err["msg"]
