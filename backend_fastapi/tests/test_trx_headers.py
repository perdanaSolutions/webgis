from uuid import UUID

from app.api.v1.endpoints.upload_jobs import group_uuid
from app.services.trx_import_service import canonical_header, canonicalize_rows

AREAL = ["Year", "Month", "Group", "AreaCode", "CompanyCode", "Estate", "UnitCode", "EstateShortName", "DivisionCode",
         "KodeBlok", "TipeBlok", "StatusTanam", "TahunTanam", "BulanTanam", "LuasTanam", "LuasTanah", "TotalPokok",
         "SPH", "JenisBibit", "JenisTopografi", "TanahDatar", "Berbukit", "Gelombang", "Curam", "JenisTanah"]
ROTASI = ["Periode", "Area", "PT", "Estate", "Afdeling", "Blok", "Luas", "Pokok", "Rotasi", "Pusingan",
          "Status Pusingan", "Bulan", "Tanggal"]


def test_all_template_headers_known_case_and_space_insensitive():
    for name in AREAL + ROTASI:
        assert canonical_header(name) == name
        assert canonical_header(f"  {name.upper()} ") == name
        assert canonical_header(name.lower().replace(" ", "_")) == name


def test_spaced_alias_maps_to_canonical():
    assert canonical_header("kode blok") == "KodeBlok"
    assert canonical_header("statuspusingan") == "Status Pusingan"
    assert canonical_header("KolomAsing") == "KolomAsing"


def test_canonicalize_rows():
    rows = canonicalize_rows([{"kodeblok": "H033", "AFDELING": "AFDI04", "x": 1}])
    assert rows == [{"KodeBlok": "H033", "Afdeling": "AFDI04", "x": 1}]


def test_group_uuid_accepts_legacy_grp_id():
    legacy = "grp-1792821442205-3b9da2b7716938"
    assert isinstance(group_uuid(legacy), UUID)
    assert group_uuid(legacy) == group_uuid(legacy)
    real = "0b7c3d1e-4f2a-4c55-9a10-1234567890ab"
    assert str(group_uuid(real)) == real
    assert group_uuid(None) is None and group_uuid("") is None
