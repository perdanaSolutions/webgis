"""Cocokkan satu blok: baris Excel (produksi, areal statement, rotasi) vs keluaran get_block_detail.

Pemakaian:  venv/Scripts/python.exe scripts/verify_excel/cek_blok.py <blok_id> <tahun> [bulan] [baris_excel_produksi]
"""
import csv
import json
import sys

from common import *  # noqa: F401,F403
from common import CACHE, F_PRODUKSI, load_prod, load_rot, load_stmt, sql
from app.db.session import SessionLocal
from app.services import block_detail_service as D

blok_id, tahun = int(sys.argv[1]), int(sys.argv[2])
bulan = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
baris = int(sys.argv[4]) if len(sys.argv) > 4 else None

m = sql(f"""SELECT e.code est, d.code dv, bl.code blk {BJ} WHERE bl.id = {blok_id}""").iloc[0]  # noqa: F405
est, dv, blk = m.est, m.dv, m.blk
print(f"Blok {blok_id} = {est}/{dv}/{blk}")

if baris:
    path = CACHE / (F_PRODUKSI.stem + ".csv")
    with open(path, encoding="utf-8") as f:
        for n, row in enumerate(csv.reader(f), start=1):
            if n in (1, baris):
                print(f"[produksi baris {n}]", row)

P = load_prod()
p = P[(P.UnitCode == est) & (P.DivisionCode == dv) & (P.KodeBlok == blk) & (P.Year == tahun)].sort_values("Month")
if bulan:
    p = p[p.Month <= bulan]
print(f"\nProduksi Excel {tahun}: {len(p)} baris, bulan {sorted(p.Month.tolist())}")
cols = ["Month", "TbsAktual", "TbsBudget", "TbsSensus", "JanjangAktual", "JanjangBudget", "JanjangSensus", "BjrAktual", "BjrBudget", "BjrSensus"]
print(p[cols].to_string(index=False))

S = load_stmt()
s = S[(S.UnitCode == est) & (S.DivisionCode == dv) & (S.KodeBlok == blk) & (S.Year == tahun)].sort_values("Month")
print("\nAreal statement (bulan terakhir):")
print(s.iloc[-1].to_string())

R = load_rot()
R["est"] = R.Estate.str.strip().str.upper()
nm = sql(f"SELECT upper(name) n FROM master.estates WHERE code = '{est}'").n[0]
r = R[(R.est == nm) & (R.Afdeling == dv) & (R.Blok == blk) & (pd.to_datetime(R.Tanggal).dt.year == tahun)]  # noqa: F405
print(f"\nRotasi Excel {tahun}: {len(r)} baris")

db = SessionLocal()
d = D.get_block_detail(db, str(blok_id), tahun=tahun, bulan=bulan)
pt = d["produksi_tbs"]
luas, trees = float(s.iloc[-1].LuasTanam), int(s.iloc[-1].TotalPokok)
sm = lambda c: float(p[c].sum(min_count=1)) if len(p) else 0.0
ta, tb, ts = sm("TbsAktual"), sm("TbsBudget"), sm("TbsSensus")
ja = sm("JanjangAktual")
rows = [
    ("tbs.aktual", ta, pt["tbs"]["aktual"]), ("tbs.budget", tb, pt["tbs"]["budget"]), ("tbs.sensus", ts, pt["tbs"]["sensus"]),
    ("janjang.aktual", int(ja), pt["janjang"]["aktual"]), ("janjang.budget", int(sm("JanjangBudget")), pt["janjang"]["budget"]),
    ("janjang.sensus", int(sm("JanjangSensus")), pt["janjang"]["sensus"]),
    ("bjr.aktual", round(ta / ja, 2) if ja else 0, pt["bjr"]["aktual"]), ("bjr.budget", round(float(p.BjrBudget.mean()), 2), pt["bjr"]["budget"]),
    ("bjr.sensus", round(float(p.BjrSensus.mean()), 2) if p.BjrSensus.notna().any() else 0, pt["bjr"]["sensus"]),
    ("luas", luas, pt["luas"]), ("ton", round(ta / 1000, 2), pt["ton"]), ("ton_ha", round(ta / 1000 / luas, 2), pt["ton_ha"]),
    ("ton_ha_budget", round(tb / 1000 / luas, 2), pt["ton_ha_budget"]), ("ton_ha_sensus", round(ts / 1000 / luas, 2), pt["ton_ha_sensus"]),
    ("kg_pkk", round(ta / trees, 2), pt["kpi_per_pokok"]["kg_pkk"]), ("jjg_pkk", round(int(ja) / trees, 2), pt["kpi_per_pokok"]["jjg_pkk"]),
]
print(f"\n{'field':18s}{'Excel':>18s}{'API':>18s}  status")
bad = 0
for name, e, g in rows:
    ok = abs(float(e) - float(g)) <= 0.011
    bad += not ok
    print(f"{name:18s}{e:18.4f}{float(g):18.4f}  {'OK' if ok else 'BEDA'}")
for _, row in p.iterrows():
    h = next(x for x in pt["data_histori"] if x["bulan"] == int(row.Month))
    e_ton = row.TbsAktual / 1000
    ok = abs(e_ton - h["ton"]) <= 0.011
    bad += not ok
    print(f"histori bulan {int(row.Month):2d}  ton Excel={e_ton:9.4f}  API={h['ton']:9.2f}  bjr Excel={row.BjrAktual:7.3f} API={h['bjr']:6.2f}  {'OK' if ok else 'BEDA'}")

if len(sys.argv) > 5:   # JSON hasil endpoint (file) untuk dibandingkan persis
    pasted = json.load(open(sys.argv[5], encoding="utf-8"))
    from app.utils.parsing import json_safe
    a, b = json.loads(json.dumps(pasted, sort_keys=True)), json.loads(json.dumps(d, default=json_safe, sort_keys=True))
    print("\nJSON tempel == keluaran service:", a == b, "" if a == b else [k for k in set(a) | set(b) if a.get(k) != b.get(k)])
print("\nTOTAL BEDA:", bad)
