"""Lapis 3: request HTTP nyata (GET saja) ke endpoint detail & history, dibandingkan dengan keluaran service."""
import os, sys, json
os.environ.pop("DB_NAME", None)
from common import sql
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.config import settings
from app.db.session import SessionLocal
from app.services import block_detail_service as D, history_service as H
from app.services.block_filter import BlockFilter
from app.utils.parsing import json_safe

print("DB:", settings.DB_NAME)
uid = sql("""SELECT u.id FROM auth.users u JOIN auth.user_roles ur ON ur.user_id=u.id JOIN auth.roles r ON r.id=ur.role_id
             WHERE r.name='superadmin' AND u.is_active ORDER BY u.created_at LIMIT 1""").id[0]
c = TestClient(app)
hd = {"Authorization": f"Bearer {create_access_token(str(uid))}"}
db = SessionLocal()
norm = lambda o: json.loads(json.dumps(o, default=json_safe, sort_keys=True))
ok = bad = 0


def cmp(name, resp, expected):
    global ok, bad
    if resp.status_code != 200:
        bad += 1; print("GAGAL", name, resp.status_code, resp.text[:150]); return
    a, b = norm(resp.json()), norm(expected)
    if a == b: ok += 1; print("OK   ", name)
    else:
        bad += 1; print("BEDA ", name, [k for k in set(a) | set(b) if a.get(k) != b.get(k)][:5])


for params in ({"blok_id": "35"}, {"blok_id": "35", "tahun": 2024}, {"blok_id": "35", "tahun": 2025, "bulan": 6}, {"blok_id": "3794", "tahun": 2025}):
    r = c.get("/api/v1/spatial/blok/detail", params=params, headers=hd)
    cmp(f"detail {params}", r, D.get_block_detail(db, params["blok_id"], tahun=params.get("tahun"), bulan=params.get("bulan")))
    if r.status_code == 200 and params == {"blok_id": "35"}:
        pt = r.json()["produksi_tbs"]
        print("     kunci produksi_tbs:", sorted(pt)[:30])
        print("     slope:", pt["slope_kemiringan_lereng"], "| total_periode:", pt["total_periode"], "| rotasi:", r.json()["rotasi_pusingan"]["total_kegiatan"])

for tbl in ("trx_produksi_tbs", "trx_rotasi_pusingan", "trx_areal_statement"):
    for extra in ({"blok_id": "35"}, {"blok_id": "35", "tahun": 2025}, {"kode_est": "E001", "tahun": 2024}, {}):
        r = c.get("/api/v1/spatial/history", params={"table": tbl, **extra}, headers=hd)
        tahun = extra.get("tahun")
        exp = H.get_history(db, tbl, tahun, BlockFilter(blok=extra.get("blok_id"), kode_est=extra.get("kode_est")))
        cmp(f"history {tbl} {extra}", r, exp)

# blok code ambigu -> harus 400 bukan 500
r = c.get("/api/v1/spatial/blok/detail", params={"blok_id": "K013"}, headers=hd); print("kode ambigu K013 ->", r.status_code, r.text[:140])
r = c.get("/api/v1/spatial/blok/detail", params={"blok_id": "99999999"}, headers=hd); print("blok tak ada ->", r.status_code)
r = c.get("/api/v1/spatial/blok/detail", params={"blok_id": "35"}); print("tanpa token ->", r.status_code)
print(f"HTTP cocok: {ok} | gagal/beda: {bad}")

sys.exit(1 if bad else 0)
