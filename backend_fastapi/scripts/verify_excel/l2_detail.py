"""Lapis 2c: GET /spatial/blok/detail (get_block_detail) vs hitungan independen dari 3 file Excel."""
import os, sys, random, collections
from common import *
from app.db.session import SessionLocal
from app.services import block_detail_service as D, history_service as H
from app.services.block_filter import BlockFilter
from app.utils.parsing import MONTH_ABBR

random.seed(21)
db = SessionLocal()
fails = []
N = 0
FIELDS = collections.Counter()


def fail(ctx, field, exp, got):
    fails.append((ctx, field, exp, got)); FIELDS[field] += 1


def near(a, b, tol=0.011):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def eq(ctx, field, exp, got, tol=None):
    ok = near(exp, got, tol) if tol is not None else exp == got
    if not ok: fail(ctx, field, exp, got)


ABBR = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Mei": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Agu": 8, "Sep": 9, "Oct": 10, "Okt": 10, "Nov": 11, "Dec": 12, "Des": 12}
S = load_stmt()
S["bk"] = list(zip(S.UnitCode, S.DivisionCode, S.KodeBlok)); S["period"] = S.Year * 100 + S.Month
S["bm"] = S.BulanTanam.astype(str).str.strip().str.capitalize().map(ABBR)
S.loc[S.TahunTanam == 0, "TahunTanam"] = np.nan
for _c in ("LuasTanam", "LuasTanah", "TotalPokok", "SPH"):
    S[_c + "_nan"] = S[_c].isna(); S[_c] = S[_c].fillna(0)
print("Excel baris dgn LuasTanam kosong:", int(S.LuasTanam_nan.sum()))
norm_soil = lambda v: {"PASIR": "TANAH PASIR"}.get(str(v).strip().upper(), str(v).strip().upper())

P = load_prod()
P["period"] = P.Year * 100 + P.Month; P["bk"] = list(zip(P.UnitCode, P.DivisionCode, P.KodeBlok)); P["k"] = list(zip(P.bk, P.period))
P0 = P.copy()
dup = P.k.duplicated(keep=False); comp = P.JanjangAktual.notna()
cc = P[dup & comp].groupby("k").size()
drop = set(cc[cc > 1].index) | (set(P.k[dup]) - set(cc.index))
P = P[(~dup | comp) & ~P.k.isin(drop)].copy()
REROUTE = {(("E017", "AFDI02", "L052"), 202410): ("E014", "AFDI02", "L052"), (("E017", "AFDI04", "K056"), 202403): ("E027", "AFDI04", "K056"),
           (("E017", "AFDI04", "I062"), 202403): ("E027", "AFDI04", "I062"), (("E017", "AFDI04", "J068"), 202403): ("E027", "AFDI04", "J068")}
ex = []
for (bk0, per), bk1 in REROUTE.items():
    r = P0[P0.bk.map(lambda v: v == bk0) & (P0.period == per) & P0.JanjangAktual.isna()].copy(); r["bk"] = [bk1]; ex.append(r)
P = pd.concat([P] + ex, ignore_index=True)

R = load_rot(); R["tgl"] = pd.to_datetime(R.Tanggal)
name2code = {r.name.strip().upper(): r.code for r in sql("select code, name from master.estates").itertuples()}
R["bk"] = list(zip(R.Estate.str.strip().str.upper().map(name2code), R.Afdeling, R.Blok)); R["period"] = R.tgl.dt.year * 100 + R.tgl.dt.month

ids = sql("select bl.id, e.code e, d.code d, bl.code b from master.blocks bl join master.divisions d on d.id=bl.division_id join master.estates e on e.id=d.estate_id")
idmap = {(r.e, r.d, r.b): int(r.id) for r in ids.itertuples()}
cat = lambda g: None if g is None else ("OPTIMUM" if g >= 0 else "GAP I" if g >= -20 else "GAP II" if g >= -40 else "GAP III")
rev = {v: k for k, v in MONTH_ABBR.items()}

Sg = {k: v.sort_values("period") for k, v in S.groupby("bk")}
Pg = {k: v for k, v in P.groupby("bk")}
Rg = {k: v.sort_values("period") for k, v in R.groupby("bk")}


def check(bk, tahun, bulan):
    global N
    N += 1
    ctx = f"DETAIL {bk} id={idmap[bk]} tahun={tahun} bulan={bulan}"
    d = D.get_block_detail(db, str(idmap[bk]), tahun=tahun, bulan=bulan)
    as_of = (tahun * 100 + (bulan or 12)) if tahun else None
    s = Sg.get(bk)
    st = None
    if s is not None:
        s2 = s[s.period <= as_of] if as_of else s
        st = s2.iloc[-1] if len(s2) else None
    info = d["informasi_blok"]
    eq(ctx, "blok_id", idmap[bk], info["blok_id"]); eq(ctx, "kode_blok", bk[2], info["kode_blok"])
    eq(ctx, "kode_est", bk[0], info["hierarki"]["kode_est"]); eq(ctx, "kode_afd", bk[1], info["hierarki"]["kode_afd"])
    # ---- master & statement
    if st is None:
        if d["areal_statement"] is not None: fail(ctx, "areal_statement", None, "ada")
    else:
        eq(ctx, "tahun_tanam", None if st.TahunTanam != st.TahunTanam else int(st.TahunTanam), info["tahun_tanam"])
        eq(ctx, "bulan_tanam", None if st.bm != st.bm else int(st.bm), rev.get(info["bulan_tanam"]))
        eq(ctx, "status_tanam", str(st.StatusTanam).strip().upper(), str(info["status_tanam"]).strip().upper())
        eq(ctx, "jenis_topografi", str(st.JenisTopografi).strip().upper(), str(info["jenis_topografi"]).strip().upper())
        eq(ctx, "jenis_tanah", norm_soil(st.JenisTanah), norm_soil(info["jenis_tanah"]))
        alias = {"CSTR": "COSTARIKA"}
        eseed = ", ".join(sorted(alias.get(p.strip(), p.strip()) for p in str(st.JenisBibit).split(",")))
        eq(ctx, "jenis_bibit", eseed, info["jenis_bibit"])
        eq(ctx, "tipe_blok", str(st.TipeBlok).strip().upper(), str(info["tipe_blok"]).strip().upper())
        eq(ctx, "kode_area", st.AreaCode, info["hierarki"]["kode_area"])
        eq(ctx, "kode_pt", str(int(st.CompanyCode)), str(info["hierarki"]["kode_pt"]))
        a = d["areal_statement"]; t = a["grand_total"]
        eq(ctx, "stmt.tahun", int(st.Year), a["tahun"])
        eq(ctx, "luas_tanam", st.LuasTanam, t["luas_tanam"], 0.0051); eq(ctx, "luas_tanah", st.LuasTanah, t["luas_tanah"], 0.0051)
        eq(ctx, "total_pokok", int(st.TotalPokok), t["total_pokok"], 0.5); eq(ctx, "sph", st.SPH, t["sph"], 0.0051)
        eq(ctx, "pct_datar", st.TanahDatar, t["pct_tanah_datar"], 0.5); eq(ctx, "pct_berbukit", st.Berbukit, t["pct_berbukit"], 0.5)
        eq(ctx, "pct_gelombang", st.Gelombang, t["pct_gelombang"], 0.5); eq(ctx, "pct_curam", st.Curam, t["pct_curam"], 0.5)
    luas = float(st.LuasTanam) if st is not None else 0.0
    trees = int(st.TotalPokok) if st is not None else 0
    # ---- periode produksi/rotasi
    p = Pg.get(bk)
    if tahun: year = tahun
    else:
        pp = p[p.period <= as_of] if (p is not None and as_of) else p
        year = int(pp.period.max() // 100) if (pp is not None and len(pp)) else None
    eq(ctx, "periode.tahun", year, d["periode"]["tahun"])
    if year:
        start = year * 100 + 1
        end = as_of if (as_of and as_of // 100 == year) else year * 100 + 12
        pr = p[(p.period >= start) & (p.period <= end)] if p is not None else pd.DataFrame(columns=P.columns)
    else:
        pr = pd.DataFrame(columns=P.columns)
    pt = d["produksi_tbs"]
    sm = lambda c: (pr[c].sum(min_count=1) if len(pr) else np.nan)
    nn = lambda v: None if v != v else float(v)
    fa, fb, fs = nn(sm("TbsAktual")), nn(sm("TbsBudget")), nn(sm("TbsSensus"))
    ja, jb, js = nn(sm("JanjangAktual")), nn(sm("JanjangBudget")), nn(sm("JanjangSensus"))
    eq(ctx, "tbs.aktual", fa or 0.0, pt["tbs"]["aktual"], 0.011); eq(ctx, "tbs.budget", fb or 0.0, pt["tbs"]["budget"], 0.011)
    eq(ctx, "tbs.sensus", fs or 0.0, pt["tbs"]["sensus"], 0.011)
    eq(ctx, "janjang.aktual", int(ja or 0), pt["janjang"]["aktual"], 0.5)
    eq(ctx, "janjang.budget", int(jb or 0), pt["janjang"]["budget"], 1.01); eq(ctx, "janjang.sensus", int(js or 0), pt["janjang"]["sensus"], 1.01)
    bjr_a = (fa / ja) if (ja and fa is not None) else nn(pr.BjrAktual.mean()) if len(pr) else None
    eq(ctx, "bjr.aktual", round(bjr_a, 2) if bjr_a is not None else 0.0, pt["bjr"]["aktual"], 0.0101)
    eq(ctx, "bjr.budget", round(pr.BjrBudget.mean(), 2) if len(pr) and pr.BjrBudget.notna().any() else 0.0, pt["bjr"]["budget"], 0.0101)
    eq(ctx, "bjr.sensus", round(pr.BjrSensus.mean(), 2) if len(pr) and pr.BjrSensus.notna().any() else 0.0, pt["bjr"]["sensus"], 0.0101)
    tb = fb or 0.0; ta = fa or 0.0
    eq(ctx, "gap_kg", round(ta - tb, 2), pt["tbs"]["gap"], 0.0101)
    eq(ctx, "kg_pkk", round(ta / trees, 2) if trees else 0.0, pt["kpi_per_pokok"]["kg_pkk"], 0.0101)
    eq(ctx, "jjg_pkk", round(int(ja or 0) / trees, 2) if trees else 0.0, pt["kpi_per_pokok"]["jjg_pkk"], 0.0101)
    ya = (ta / 1000 / luas) if (luas and fa is not None) else None
    yb = (tb / 1000 / luas) if (luas and fb is not None) else None
    ys = ((fs or 0) / 1000 / luas) if (luas and fs is not None) else None
    gb = None if (ya is None or not yb) else (ya - yb) / yb * 100
    gs = None if (ya is None or not ys) else (ya - ys) / ys * 100
    eq(ctx, "luas", round(luas, 2), pt["luas"], 0.0101); eq(ctx, "ton", round(ta / 1000, 2), pt["ton"], 0.0101)
    eq(ctx, "ton_ha", round(ya, 2) if ya is not None else 0.0, pt["ton_ha"], 0.0101)
    eq(ctx, "ton_ha_budget", yb, pt["ton_ha_budget"], 0.0101); eq(ctx, "ton_ha_sensus", ys, pt["ton_ha_sensus"], 0.0101)
    eq(ctx, "gap_budget_pct", gb, pt["gap_budget_pct"], 0.0101); eq(ctx, "gap_sensus_pct", gs, pt["gap_sensus_pct"], 0.0101)
    eq(ctx, "kategori_budget", cat(gb), pt["kategori_budget"]); eq(ctx, "kategori_sensus", cat(gs), pt["kategori_sensus"])
    # ---- struktur sama dgn history (+ slope) untuk blok & tahun yang sama
    h = H.get_history(db, "trx_produksi_tbs", year, BlockFilter(blok=str(idmap[bk])))
    for k in ("slope_kemiringan_lereng", "slope_kemiringan_lereng_ha", "data_histori", "ringkasan_gap_budget", "ringkasan_gap_sensus", "mode_akumulasi", "total_periode"):
        if pt.get(k) != h.get(k): fail(ctx, "sama_dgn_history:" + k, h.get(k), pt.get(k))
    # slope vs Excel (statement terbaru <= akhir tahun 'year' / as_of history)
    if st is not None and year:
        s3 = s[s.Year <= year]
        if len(s3):
            s3 = s3.iloc[-1]
            for lab, col in (("0-3%", "TanahDatar"), ("3-8%", "Gelombang"), ("8-15%", "Berbukit"), ("15-25%", "Curam")):
                eq(ctx, "slope " + lab, s3.LuasTanam * s3[col] / 100, pt["slope_kemiringan_lereng_ha"][lab], 0.0101)
    # ---- rotasi
    rr = Rg.get(bk)
    if year and rr is not None:
        rr = rr[(rr.period >= year * 100 + 1) & (rr.period <= end)]
    else:
        rr = pd.DataFrame(columns=R.columns)
    lst = d["rotasi_pusingan"]["daftar_rotasi"]
    eq(ctx, "rotasi.total", len(rr), d["rotasi_pusingan"]["total_kegiatan"])
    if len(rr) == len(lst):
        for (_, e), g in zip(rr.iterrows(), lst):
            c2 = ctx + f" rot {g['tanggal']}"
            eq(c2, "rot.tanggal", e.tgl.strftime("%Y-%m-%d"), str(g["tanggal"])[:10])
            eq(c2, "rot.rotasi_ke", float(e.Rotasi), float(g["rotasi_ke"]), 0.011); eq(c2, "rot.pusingan", int(e.Pusingan), g["pusingan_hari"], 0.5)
            es = None if str(e["Status Pusingan"]).strip() in ("(Blanks)", "") else str(e["Status Pusingan"]).strip()
            eq(c2, "rot.status", es, g["status_pusingan"]); eq(c2, "rot.luas", float(e.Luas), g["luas"], 0.0051); eq(c2, "rot.pokok", int(e.Pokok), g["pokok"], 0.5)


all_blocks = sorted(set(S.bk) | set(P.bk))
no_prod = sorted(set(S.bk) - set(P.bk))
rot_blocks = sorted(set(R.bk))
special = [("E001", "AFDI01", "K013")] + sorted({v for v in REROUTE.values()} | {k[0] for k in REROUTE})
combos = [(None, None), (2024, None), (2025, None), (2025, 6), (2026, None)]
for bk in special:
    for c in combos: check(bk, *c)
for bk in rot_blocks:
    for y in [None] + list(range(2018, 2027)): check(bk, y, None)
    check(bk, 2024, 3); check(bk, 2025, 10)
for bk in random.sample(no_prod, min(10, len(no_prod))):
    for c in combos[:3]: check(bk, *c)
for bk in random.sample(all_blocks, 250):
    for c in combos[:4]: check(bk, *c)
print(f"[detail] skenario: {N} | selisih: {len(fails)}")
print("selisih per field:", dict(FIELDS))
for f in fails[:30]: print("  ", f)
print("blok tanpa produksi:", len(no_prod), "| blok rotasi:", len(rot_blocks))

sys.exit(1 if fails else 0)
