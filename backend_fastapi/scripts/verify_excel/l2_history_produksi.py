"""Lapis 2: respons GET /history (trx_produksi_tbs, trx_areal_statement, trx_rotasi_pusingan) vs hitungan independen dari Excel."""
import os, sys, random
from common import *
from app.db.session import SessionLocal
from app.services import history_service as H
from app.services.block_filter import BlockFilter

random.seed(7)
db = SessionLocal()

# ---------- data Excel ----------
S = load_stmt()
S["period"] = S.Year * 100 + S.Month
S["bk"] = list(zip(S.UnitCode, S.DivisionCode, S.KodeBlok))
P = load_prod()
P["period"] = P.Year * 100 + P.Month
P["bk"] = list(zip(P.UnitCode, P.DivisionCode, P.KodeBlok))
# aturan dedupe migrasi: kunci ganda -> pakai baris lengkap (ada janjang aktual); bila tidak tunggal -> tidak dimuat
P["k"] = list(zip(P.bk, P.period))
P0 = P.copy()
dupk = P.k[P.k.duplicated(keep=False)]
P["dup"] = P.k.isin(set(dupk))
P["complete"] = P.JanjangAktual.notna()
keep = (~P.dup) | (P.dup & P.complete)
cnt_complete = P[P.dup & P.complete].groupby("k").size()
drop_conf = set(cnt_complete[cnt_complete > 1].index) | (set(P.k[P.dup]) - set(cnt_complete.index))
P = P[keep & ~P.k.isin(drop_conf)].copy()
REROUTE = {(("E017","AFDI02","L052"),202410): ("E014","AFDI02","L052"), (("E017","AFDI04","K056"),202403): ("E027","AFDI04","K056"),
           (("E017","AFDI04","I062"),202403): ("E027","AFDI04","I062"), (("E017","AFDI04","J068"),202403): ("E027","AFDI04","J068")}
extra = []
for (bk0, per), bk1 in REROUTE.items():
    r = P0[P0.bk.map(lambda v: v == bk0) & (P0.period == per) & P0.JanjangAktual.isna()]
    assert len(r) == 1, (bk0, per, len(r))
    r = r.copy(); r["bk"] = [bk1]; extra.append(r)
P = pd.concat([P] + extra, ignore_index=True)
print("Produksi Excel setelah aturan dedupe:", len(P), "| kunci dikeluarkan (konflik):", len(drop_conf))

# kunci yg beda routing di DB (baris E017 lengkap-tidak, tersimpan di estate lain) -> dicatat sbg pengecualian
KNOWN_EXC = {("AFDI02", "L052"), ("AFDI04", "I062"), ("AFDI04", "J068"), ("AFDI04", "K056")}

SM = S.set_index(["bk", "period"])
PM = P.drop(columns=["LuasTanam"]).merge(S[["bk", "period", "LuasTanam", "TotalPokok"]], on=["bk", "period"], how="left")

rows_fail = []
checked = 0

def gap(a, t):
    return None if a is None or not t else (a - t) / t * 100

def cat(g):
    if g is None: return None
    return "OPTIMUM" if g >= 0 else "GAP I" if g >= -20 else "GAP II" if g >= -40 else "GAP III"

def near(a, b, tol=0.011):
    if a is None or b is None: return a is None and b is None
    return abs(float(a) - float(b)) <= tol

def fail(ctx, field, exp, got):
    rows_fail.append((ctx, field, exp, got))

def expected_prod(sel_bk, tahun):
    """sel_bk: set blok (estate,div,blok). Kembalikan dict periode -> metrik."""
    pm = PM[PM.bk.isin(sel_bk)]
    if tahun: pm = pm[pm.Year == tahun]
    if pm.empty: return {}, None
    g = pm.groupby("period").agg(ffb=("TbsAktual", lambda x: x.sum(min_count=1)), bgt=("TbsBudget", lambda x: x.sum(min_count=1)), sns=("TbsSensus", lambda x: x.sum(min_count=1)),
                                 bun=("JanjangAktual", lambda x: x.sum(min_count=1)), area=("LuasTanam", lambda x: x.sum(min_count=1)), trees=("TotalPokok", lambda x: x.sum(min_count=1))).reset_index()
    g["Y"] = g.period // 100; g["M"] = g.period % 100
    key = "M" if tahun else "Y"
    out = {}
    for k, s in g.groupby(key):
        luas = s.area.mean(); trees = s.trees.mean()
        luas = 0.0 if luas != luas else luas
        trees = None if (trees != trees) else trees
        nn = lambda v: None if v != v else v
        fa, fb, fs = nn(s.ffb.sum(min_count=1)), nn(s.bgt.sum(min_count=1)), nn(s.sns.sum(min_count=1))
        ton = (fa or 0) / 1000
        ya = (fa / 1000 / luas) if (luas and fa is not None) else None
        yb = (fb / 1000 / luas) if (luas and fb is not None) else None
        ys = (fs / 1000 / luas) if (luas and fs is not None) else None
        gb, gs = gap(ya, yb), gap(ya, ys)
        bun = nn(s.bun.sum(min_count=1))
        out[int(k)] = dict(luas=luas, ton=ton, ton_ha=ya or 0, ton_ha_budget=yb, ton_ha_sensus=ys, gap_budget_pct=gb, gap_sensus_pct=gs,
                           kategori_budget=cat(gb), kategori_sensus=cat(gs),
                           bjr=(fa / bun) if (bun and fa is not None) else 0,
                           jjg_ppk=(bun / trees) if (trees and bun is not None) else None,
                           kg_ppk=(fa / trees) if (trees and fa is not None) else None)
    return out, pm

def expected_slope(sel_bk, tahun):
    s = S[S.bk.isin(sel_bk)]
    if tahun: s = s[s.Year <= tahun]
    s = s.sort_values("period").groupby("bk").tail(1)
    return [(s.LuasTanam * s[c] / 100).sum() for c in ("TanahDatar", "Gelombang", "Berbukit", "Curam")]

def expected_gap(sel_bk, tahun, tgt_col):
    pm = PM[PM.bk.isin(sel_bk)]
    if tahun: pm = pm[pm.Year == tahun]
    if pm.empty: return None
    last = pm.period.max()
    pm = pm[pm.period == last].groupby("bk").agg(a=("TbsAktual", "sum"), t=(tgt_col, "sum"), l=("LuasTanam", "sum"))
    res = {n: [0.0, 0] for n in ("OPTIMUM", "GAP I", "GAP II", "GAP III")}
    for _, r in pm.iterrows():
        c = cat(gap(r.a, r.t))
        if c: res[c][0] += r.l if r.l == r.l else 0; res[c][1] += 1
    return last, res

def check_prod(ctx, flt_kwargs, sel_bk, tahun):
    global checked
    got = H.get_history(db, "trx_produksi_tbs", tahun, BlockFilter(**flt_kwargs))
    exp, pm = expected_prod(sel_bk, tahun)
    gd = {r["periode"]: r for r in got["data_histori"]}
    checked += 1
    if set(gd) != set(exp): fail(ctx, "periode", sorted(exp), sorted(gd)); return
    for k, e in exp.items():
        g = gd[k]
        for f, v in e.items():
            if isinstance(v, str) or v is None or g[f] is None:
                if v != g[f]: fail(ctx + f" p={k}", f, v, g[f])
            elif not near(v, g[f], 0.011 if f not in ("kg_ppk",) else 0.6): fail(ctx + f" p={k}", f, round(v, 3), g[f])
    sl = expected_slope(sel_bk, tahun)
    for c, v in zip(("0-3%", "3-8%", "8-15%", "15-25%"), sl):
        if not near(v, got["slope_kemiringan_lereng_ha"][c], 0.011): fail(ctx, "slope " + c, round(v, 3), got["slope_kemiringan_lereng_ha"][c])
    for tgt, col, key in (("budget", "TbsBudget", "ringkasan_gap_budget"), ("sensus", "TbsSensus", "ringkasan_gap_sensus")):
        eg = expected_gap(sel_bk, tahun, col); gg = got[key]
        if eg is None:
            if gg is not None: fail(ctx, key, None, "ada")
            continue
        last, res = eg
        if (gg["periode"]["tahun"], gg["periode"]["bulan"]) != (last // 100, last % 100): fail(ctx, key + " periode", last, gg["periode"])
        for c in gg["kategori"]:
            if c["jumlah_blok"] != res[c["kategori"]][1] or not near(c["luas"], res[c["kategori"]][0], 0.011):
                fail(ctx, f"{key} {c['kategori']}", res[c["kategori"]], (c["luas"], c["jumlah_blok"]))

# ---------- peta filter ----------
blk_all = set(S.bk) | set(P.bk)
est2co = S.drop_duplicates('UnitCode').set_index('UnitCode').CompanyCode.to_dict()
UALL = pd.DataFrame({'bk': sorted(blk_all)}); UALL['est'] = UALL.bk.map(lambda b: b[0])
scopes = []
scopes.append(("SEMUA", {}, blk_all))
for a in sorted(S.AreaCode.unique()):
    scopes.append((f"area={a}", {"area": a}, set(S[S.AreaCode == a].bk)))
for c in sorted(S.CompanyCode.unique()):
    scopes.append((f"pt={c}", {"kode_pt": str(c)}, set(UALL[UALL.est.map(est2co) == c].bk)))
for e in sorted(S.UnitCode.unique()):
    scopes.append((f"est={e}", {"kode_est": e}, set(UALL[UALL.est == e].bk)))
for t in sorted(S.TipeBlok.dropna().unique()):
    scopes.append((f"ownership={t}", {"ownership": t}, set(S[S.TipeBlok == t].bk)))
afd = sorted({(b[0], b[1]) for b in blk_all})
for e, d in random.sample(afd, min(25, len(afd))):
    scopes.append((f"est={e} afd={d}", {"kode_est": e, "kode_afd": d}, {b for b in blk_all if b[0] == e and b[1] == d}))
for bk in random.sample(sorted(blk_all), 120):
    bid = sql(f"select bl.id from master.blocks bl join master.divisions d on d.id=bl.division_id join master.estates e on e.id=d.estate_id where e.code='{bk[0]}' and d.code='{bk[1]}' and bl.code='{bk[2]}'").id[0]
    scopes.append((f"blok {bk} id={bid}", {"blok": str(bid)}, {bk}))

# area filter in DB memakai area terbaru blok; Excel AreaCode bisa berubah antar bulan -> pakai area terbaru juga
latest_area = S.sort_values("period").groupby("bk").tail(1).set_index("bk").AreaCode
for i, (n, kw, sel) in enumerate(scopes):
    if n.startswith("area="):
        scopes[i] = (n, kw, set(latest_area[latest_area == kw["area"]].index))

for n, kw, sel in scopes:
    for tahun in (None, 2024, 2025):
        check_prod(f"PRODUKSI {n} tahun={tahun}", kw, sel, tahun)

print(f"[produksi] skenario diuji: {checked} | selisih: {len(rows_fail)}")

# ---------- ringkas kegagalan ----------
import collections
by_field = collections.Counter(f[1].split(" ")[0] for f in rows_fail)
print("selisih per field:", dict(by_field))
for f in rows_fail[:25]:
    print("  ", f)

sys.exit(1 if rows_fail else 0)
