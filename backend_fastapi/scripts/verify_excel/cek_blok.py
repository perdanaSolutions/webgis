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
    p = p[p.Month == bulan]
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
info = d["informasi_blok"]
month = d["periode"]["bulan"]
if month:
    p = p[p.Month == month]
    s = s[s.Month == month] if len(s) else s
luas = round(float(s.iloc[-1].LuasTanam), 2) if len(s) else 0.0
sm = lambda c: round(float(p[c].sum()), 2) if len(p) and p[c].notna().any() else 0.0
avg = lambda c: round(float(p[c].mean()), 2) if len(p) and p[c].notna().any() else 0.0
ta, tb, ts = sm("TbsAktual"), sm("TbsBudget"), sm("TbsSensus")
yld = (lambda kg: round(kg / 1000 / luas, 2) if luas else 0.0)

def gap(actual, target):
    if not target:
        return 0.0
    value = round((actual - target) / target * 100, 2)
    return 0.0 if value == 0 else value

ya, yb, ys = yld(ta), yld(tb), yld(ts)
rows = [
    ("tbs.aktual", ta, info["tbs"]["aktual"]), ("tbs.budget", tb, info["tbs"]["budget"]), ("tbs.sensus", ts, info["tbs"]["sensus"]),
    ("jjg.aktual", int(sm("JanjangAktual")), info["jjg"]["aktual"]),
    ("jjg.budget", int(sm("JanjangBudget")), info["jjg"]["budget"]),
    ("jjg.sensus", int(sm("JanjangSensus")), info["jjg"]["sensus"]),
    ("bjr.aktual", avg("BjrAktual"), info["bjr"]["aktual"]),
    ("bjr.budget", avg("BjrBudget"), info["bjr"]["budget"]),
    ("bjr.sensus", avg("BjrSensus"), info["bjr"]["sensus"]),
    ("luas_tanam", luas, info["luas_tanam"]),
    ("yield.aktual", ya, info["yield"]["aktual"]),
    ("yield.budget", yb, info["yield"]["budget"]),
    ("yield.sensus", ys, info["yield"]["sensus"]),
    ("gap_act_bgt", gap(ya, yb), info["gap_act_bgt"]["value"]),
    ("gap_act_sns", gap(ya, ys), info["gap_act_sns"]["value"]),
]
print(f"\n{'field':18s}{'Excel':>18s}{'API':>18s}  status")
bad = 0
for name, e, g in rows:
    ok = abs(float(e) - float(g)) <= 0.011
    bad += not ok
    print(f"{name:18s}{e:18.4f}{float(g):18.4f}  {'OK' if ok else 'BEDA'}")
print("kategori budget:", info["gap_act_bgt"]["kategori"], "| kategori sensus:", info["gap_act_sns"]["kategori"])

if len(sys.argv) > 5:   # JSON hasil endpoint (file) untuk dibandingkan persis
    pasted = json.load(open(sys.argv[5], encoding="utf-8"))
    from app.utils.parsing import json_safe
    a, b = json.loads(json.dumps(pasted, sort_keys=True)), json.loads(json.dumps(d, default=json_safe, sort_keys=True))
    print("\nJSON tempel == keluaran service:", a == b, "" if a == b else [k for k in set(a) | set(b) if a.get(k) != b.get(k)])
print("\nTOTAL BEDA:", bad)
