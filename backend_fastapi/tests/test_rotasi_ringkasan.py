from app.services.history_service import rotation_summary


def _r(tahun, bulan, tanam, panen):
    return {"tahun": tahun, "bulan": bulan, "total_luas_rotasi": tanam, "luas_panen": panen}


def test_rotasi_total_luas_panen_dibagi_luas_tanam_bulan_terakhir():
    rows = [_r(2026, 1, 100, 300), _r(2026, 2, 120, 360)]
    s = rotation_summary(rows)
    assert s == {"luas_panen": 660.0, "luas_tanam": 120.0, "rotasi": 5.5,
                 "periode_luas_tanam": {"tahun": 2026, "bulan": 2}}


def test_rotasi_kosong_dan_luas_nol():
    assert rotation_summary([]) is None
    assert rotation_summary([_r(2026, 1, 0, 0)])["rotasi"] is None
