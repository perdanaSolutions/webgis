"""Lapis 2b: GET /history trx_areal_statement & trx_rotasi_pusingan vs hitungan independen dari Excel."""
import os, sys, random, collections
from common import *
from app.db.session import SessionLocal
from app.services import history_service as H
from app.services.block_filter import BlockFilter

random.seed(11)
db = SessionLocal()
fails = []
n_checked = 0


def near(a, b, tol=0.011):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def fail(ctx, field, exp, got):
    fails.append((ctx, field, exp, got))


ABBR = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Mei": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Agu": 8,
        "Sep": 9, "Oct": 10, "Okt": 10, "Nov": 11, "Dec": 12, "Des": 12}
S = load_stmt()
S["bk"] = list(zip(S.UnitCode, S.DivisionCode, S.KodeBlok))
S["period"] = S.Year * 100 + S.Month
S["bm"] = S.BulanTanam.astype(str).str.strip().str.capitalize().map(ABBR)
S.loc[S.TahunTanam == 0, "TahunTanam"] = np.nan   # 0 = belum ditanam -> NULL di DB
norm_soil = lambda v: {"PASIR": "TANAH PASIR"}.get(str(v).strip().upper(), str(v).strip().upper())
S["soil"] = S.JenisTanah.map(norm_soil)
S["topo"] = S.JenisTopografi.astype(str).str.strip().str.upper()
SEED_ALIAS = {"CSTR": "COSTARIKA"}   # alias di ref.value_aliases
S["seed"] = S.JenisBibit.astype(str).map(lambda v: ", ".join(sorted(SEED_ALIAS.get(p.strip(), p.strip()) for p in v.split(","))))

# ---------- AREAL STATEMENT ----------
def exp_areal(sel, tt):
    s = S[S.bk.isin(sel)]
    snap = s.sort_values("period").groupby(["bk", "Year"]).tail(1)
    end_tt = snap.TahunTanam.max()
    end_tt = 0 if end_tt != end_tt else int(end_tt)
    lo, hi = (tt, tt) if tt else (end_tt - 4, end_tt)
    f = snap[(snap.TahunTanam >= lo) & (snap.TahunTanam <= hi)]
    return f

def check_areal(ctx, kw, sel, tt):
    global n_checked
    n_checked += 1
    got = H.get_history(db, "trx_areal_statement", None, BlockFilter(**kw)) if tt is None else None
    if tt is not None:
        # tahun_tanam dipasang lewat parameter ke-2 (kolom `tahun`) pada get_history
        got = H.get_history(db, "trx_areal_statement", tt, BlockFilter(**kw))
    f = exp_areal(sel, tt)
    got_by_year = {d["tahun"]: d["groups"] for d in got["data"]}
    exp_years = sorted(f.Year.unique(), reverse=True)
    if sorted(got_by_year, reverse=True) != [int(y) for y in exp_years]:
        fail(ctx, "tahun", [int(y) for y in exp_years], sorted(got_by_year, reverse=True)); return
    for y in exp_years:
        fy = f[f.Year == y]
        gs = got_by_year[int(y)]
        # total per tahun
        tot = lambda key: sum(g["totals"][key] for g in gs)
        pairs = [("count_records", len(fy)), ("luas_tanam", fy.LuasTanam.sum()), ("luas_tanah", fy.LuasTanah.sum()), ("total_pokok", fy.TotalPokok.sum())]
        for key, ev in pairs:
            if not near(tot(key), ev, 0.05 + 0.001 * len(gs)):   # tiap grup dibulatkan 2 desimal
                fail(ctx + f" y={y}", key, round(ev, 3), tot(key))
        # per grup
        eg = {}
        for _, r in fy.iterrows():
            k = (str(r.StatusTanam).strip().upper(), None if r.bm != r.bm else int(r.bm), None if r.TahunTanam != r.TahunTanam else int(r.TahunTanam),
                 r.seed, r.topo, r.soil)
            a = eg.setdefault(k, [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            a[0] += 1; a[1] += r.LuasTanam; a[2] += r.LuasTanah; a[3] += r.TotalPokok
            a[4] += r.TanahDatar; a[5] += r.Berbukit; a[6] += r.Gelombang; a[7] += r.Curam
        gg = {}
        rev = {v: k for k, v in H.MONTH_ABBR.items()} if hasattr(H, "MONTH_ABBR") else {}
        from app.utils.parsing import MONTH_ABBR
        rev = {v: k for k, v in MONTH_ABBR.items()}
        for g in gs:
            gk = g["group_keys"]
            key = (str(gk["status_tanam"]).strip().upper(), rev.get(gk["bulan_tanam"]), gk["tahun_tanam"],
                   str(gk["jenis_bibit"]).strip() if gk["jenis_bibit"] is not None else "nan", str(gk["jenis_topografi"]).strip().upper(), norm_soil(gk["jenis_tanah"]))
            gg[key] = g["totals"]
        if set(eg) != set(gg):
            fail(ctx + f" y={y}", "group_keys", sorted(map(str, set(eg) - set(gg)))[:3], sorted(map(str, set(gg) - set(eg)))[:3]); continue
        for k, a in eg.items():
            t = gg[k]; c = a[0]
            if t["count_records"] != c: fail(ctx + f" y={y} {k}", "count", c, t["count_records"])
            if not near(t["luas_tanam"], a[1]): fail(ctx + f" y={y} {k}", "luas_tanam", a[1], t["luas_tanam"])
            if not near(t["luas_tanah"], a[2]): fail(ctx + f" y={y} {k}", "luas_tanah", a[2], t["luas_tanah"])
            if t["total_pokok"] != int(round(a[3])): fail(ctx + f" y={y} {k}", "total_pokok", a[3], t["total_pokok"])
            for nm, v in zip(("pct_tanah_datar", "pct_berbukit", "pct_gelombang", "pct_curam"), a[4:8]):
                if not near(t[nm], v / c, 0.011): fail(ctx + f" y={y} {k}", nm, v / c, t[nm])
    # grand total = tahun terbaru
    if len(exp_years):
        y0 = int(exp_years[0]); fy = f[f.Year == y0]
        gt = got["grand_total"]
        if not near(gt["luas_tanam"], fy.LuasTanam.sum(), 0.05 + 0.001 * len(got_by_year[y0])): fail(ctx, "grand luas_tanam", fy.LuasTanam.sum(), gt["luas_tanam"])
        if not near(gt["luas_tanah"], fy.LuasTanah.sum(), 0.05 + 0.001 * len(got_by_year[y0])): fail(ctx, "grand luas_tanah", fy.LuasTanah.sum(), gt["luas_tanah"])
        if gt["total_pokok"] != int(round(fy.TotalPokok.sum())) and abs(gt["total_pokok"] - fy.TotalPokok.sum()) > len(got_by_year[y0]): fail(ctx, "grand total_pokok", fy.TotalPokok.sum(), gt["total_pokok"])
        for nm, col in (("pct_tanah_datar", "TanahDatar"), ("pct_berbukit", "Berbukit"), ("pct_gelombang", "Gelombang"), ("pct_curam", "Curam")):
            if not near(gt[nm], fy[col].mean(), 0.011): fail(ctx, "grand " + nm, fy[col].mean(), gt[nm])
    # daftar tahun tanam
    yrs = H.list_planting_years(db, BlockFilter(**kw))
    ey = sorted({int(v) for v in S[S.bk.isin(sel)].TahunTanam.dropna()}, reverse=True)
    if yrs != ey: fail(ctx, "list_tahun_tanam", ey[:5], yrs[:5])


blk_all = set(S.bk)
latest_area = S.sort_values("period").groupby("bk").tail(1).set_index("bk").AreaCode
scopes = [("SEMUA", {}, blk_all)]
for a in sorted(S.AreaCode.unique()):
    scopes.append((f"area={a}", {"area": a}, set(latest_area[latest_area == a].index)))
for c in sorted(S.CompanyCode.unique()):
    scopes.append((f"pt={c}", {"kode_pt": str(c)}, set(S[S.CompanyCode == c].bk)))
for e in sorted(S.UnitCode.unique()):
    scopes.append((f"est={e}", {"kode_est": e}, set(S[S.UnitCode == e].bk)))
for t in sorted(S.TipeBlok.dropna().unique()):
    scopes.append((f"ownership={t}", {"ownership": t}, set(S[S.TipeBlok == t].bk)))
afd = S[["UnitCode", "DivisionCode"]].drop_duplicates().values.tolist()
for e, d in random.sample(afd, 15):
    scopes.append((f"est={e} afd={d}", {"kode_est": e, "kode_afd": d}, set(S[(S.UnitCode == e) & (S.DivisionCode == d)].bk)))
ids = sql("select bl.id, e.code e, d.code d, bl.code b from master.blocks bl join master.divisions d on d.id=bl.division_id join master.estates e on e.id=d.estate_id")
idmap = {(r.e, r.d, r.b): r.id for r in ids.itertuples()}
for bk in random.sample(sorted(blk_all), 60):
    scopes.append((f"blok {bk}", {"blok": str(idmap[bk])}, {bk}))

for n, kw, sel in scopes:
    check_areal(f"AREAL {n} tt=None", kw, sel, None)
for n, kw, sel in random.sample(scopes, 25):
    tts = sorted({int(v) for v in S[S.bk.isin(sel)].TahunTanam.dropna()})
    if tts:
        check_areal(f"AREAL {n} tt={tts[len(tts)//2]}", kw, sel, tts[len(tts) // 2])
print(f"[areal] skenario: {n_checked} | selisih: {len(fails)}")
for f in fails[:15]: print("  ", f)
areal_fail = len(fails)

# ---------- ROTASI ----------
R = load_rot()
R["tgl"] = pd.to_datetime(R.Tanggal)
R["Y"] = R.tgl.dt.year; R["M"] = R.tgl.dt.month
est = sql("select code, name from master.estates")
name2code = {r.name.strip().upper(): r.code for r in est.itertuples()}
R["est"] = R.Estate.str.strip().str.upper().map(name2code)
assert R.est.notna().all(), R[R.est.isna()].Estate.unique()
R["bk"] = list(zip(R.est, R.Afdeling, R.Blok))
n0 = n_checked


def check_rot(ctx, kw, sel, tahun):
    global n_checked
    n_checked += 1
    got = H.get_history(db, "trx_rotasi_pusingan", tahun, BlockFilter(**kw))
    r = R[R.bk.isin(sel)]
    if tahun: r = r[r.Y == tahun]
    key = "M" if tahun else "Y"
    exp = {}
    for k, g in r.groupby(key):
        exp[int(k)] = dict(total_rotasi=len(g), rotasi_terakhir=float(g.Rotasi.max()), avg_pusingan_hari=round(float(g.Pusingan.mean()), 2),
                           total_luas_rotasi=float(g.Luas.sum()), total_pokok_rotasi=int(g.Pokok.sum()))
    gd = {(d["bulan"] if tahun else d["tahun"]): d for d in got["data"]}
    if set(gd) != set(exp): fail(ctx, "periode", sorted(exp), sorted(gd)); return
    for k, e in exp.items():
        g = gd[k]
        for f, v in e.items():
            tol = 0.011 if f != "total_pokok_rotasi" else 0.5
            if not near(g[f], v, tol): fail(ctx + f" p={k}", f, v, g[f])


rsc = [("SEMUA", {}, set(R.bk))]
for e in sorted(R.est.unique()):
    rsc.append((f"est={e}", {"kode_est": e}, set(R[R.est == e].bk)))
for e, d in R[["est", "Afdeling"]].drop_duplicates().values.tolist():
    rsc.append((f"est={e} afd={d}", {"kode_est": e, "kode_afd": d}, set(R[(R.est == e) & (R.Afdeling == d)].bk)))
for bk in sorted(set(R.bk)):
    rsc.append((f"blok {bk}", {"blok": str(idmap[bk])}, {bk}))
for n, kw, sel in rsc:
    for tahun in [None] + list(range(2018, 2027)):
        check_rot(f"ROTASI {n} tahun={tahun}", kw, sel, tahun)
print(f"[rotasi] skenario: {n_checked - n0} | selisih total kumulatif: {len(fails) - areal_fail}")
for f in fails[areal_fail:areal_fail + 15]: print("  ", f)
print("TOTAL skenario:", n_checked, "TOTAL selisih:", len(fails))

sys.exit(1 if fails else 0)
