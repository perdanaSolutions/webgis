"""Lapis 2c: GET /spatial/blok/detail (get_block_detail) vs hitungan independen dari 3 file Excel."""
import os, sys, random, collections
from common import *
from app.db.session import SessionLocal
from app.services import block_detail_service as D
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
def cat(g):
    if g < -40:
        return "GAP III"
    if -40 <= g <= -20:
        return "GAP II"
    if -20 < g < 0:
        return "GAP I"
    if g > 0:
        return "OPTIMUM"
    return ""
rev = {v: k for k, v in MONTH_ABBR.items()}

Sg = {k: v.sort_values("period") for k, v in S.groupby("bk")}
Pg = {k: v for k, v in P.groupby("bk")}
def _period_of(bk, tahun, bulan):
    """Periode yang dipakai API: bulan+tahun persis, selain itu bulan terakhir yang ada."""
    if tahun and bulan:
        return tahun * 100 + bulan
    cap = tahun * 100 + 12 if tahun else None
    found = []
    for frame in (Sg.get(bk), Pg.get(bk)):
        if frame is None or not len(frame):
            continue
        vals = frame.period
        if cap:
            vals = vals[vals <= cap]
        if len(vals):
            found.append(int(vals.max()))
    return max(found) if found else None


def check(bk, tahun, bulan):
    global N
    N += 1
    ctx = f"DETAIL {bk} id={idmap[bk]} tahun={tahun} bulan={bulan}"
    d = D.get_block_detail(db, str(idmap[bk]), tahun=tahun, bulan=bulan)
    period = _period_of(bk, tahun, bulan)
    s = Sg.get(bk)
    st = None
    if s is not None and period:
        hit = s[s.period == period]
        st = hit.iloc[-1] if len(hit) else None
    info = d["informasi_blok"]
    eq(ctx, "blok_id", idmap[bk], info["blok_id"]); eq(ctx, "kode_blok", bk[2], info["kode_blok"])
    eq(ctx, "kode_est", bk[0], info["hierarki"]["kode_est"]); eq(ctx, "kode_afd", bk[1], info["hierarki"]["kode_afd"])
    eq(ctx, "mode", "PERIODE_BULAN_TAHUN", d["mode"])
    if tahun and bulan:
        eq(ctx, "periode.bulan", bulan, d["periode"]["bulan"])
        eq(ctx, "periode.tahun", tahun, d["periode"]["tahun"])
        eq(ctx, "label", f"Tahun {tahun}", d["periode"]["label_periode"])
    elif period:
        eq(ctx, "periode.bulan", period % 100, d["periode"]["bulan"])
        eq(ctx, "periode.tahun", period // 100, d["periode"]["tahun"])
    # ---- master & statement periode yang sama
    if st is None:
        eq(ctx, "tahun_tanam", None, info["tahun_tanam"])
        eq(ctx, "luas_tanam", 0.0, info["luas_tanam"], 0.0051)
        eq(ctx, "luas_tanah", 0.0, info["luas_tanah"], 0.0051)
        eq(ctx, "pokok", 0, info["pokok"])
        eq(ctx, "sph", 0.0, info["sph"], 0.0051)
    else:
        eq(ctx, "tahun_tanam", None if st.TahunTanam != st.TahunTanam else int(st.TahunTanam), info["tahun_tanam"])
        eq(ctx, "bulan_tanam", None if st.bm != st.bm else int(st.bm), rev.get(info["bulan_tanam"]))
        eq(ctx, "status_tanam", str(st.StatusTanam).strip().upper(), str(info["status_tanam"]).strip().upper())
        eq(ctx, "jenis_topografi", str(st.JenisTopografi).strip().upper(), str(info["jenis_topografi"]).strip().upper())
        eq(ctx, "jenis_tanah", norm_soil(st.JenisTanah), norm_soil(info["jenis_tanah"]))
        alias = {"CSTR": "COSTARIKA"}
        eseed = ", ".join(sorted(alias.get(part.strip(), part.strip()) for part in str(st.JenisBibit).split(",")))
        eq(ctx, "jenis_bibit", eseed, info["jenis_bibit"])
        eq(ctx, "tipe_blok", str(st.TipeBlok).strip().upper(), str(info["tipe_blok"]).strip().upper())
        eq(ctx, "kode_area", st.AreaCode, info["hierarki"]["kode_area"])
        eq(ctx, "kode_pt", str(int(st.CompanyCode)), str(info["hierarki"]["kode_pt"]))
        eq(ctx, "luas_tanam", round(float(st.LuasTanam), 2), info["luas_tanam"], 0.0051)
        eq(ctx, "luas_tanah", round(float(st.LuasTanah), 2), info["luas_tanah"], 0.0051)
        eq(ctx, "pokok", int(st.TotalPokok), info["pokok"], 0.5)
        eq(ctx, "sph", round(float(st.SPH), 2), info["sph"], 0.0051)
    luas = round(float(st.LuasTanam), 2) if st is not None else 0.0
    # ---- produksi satu periode (bukan akumulasi tahun)
    src = Pg.get(bk)
    pr = src[src.period == period] if (src is not None and period) else pd.DataFrame(columns=P.columns)

    def summed(column):
        if not len(pr) or not pr[column].notna().any():
            return 0.0
        return round(float(pr[column].sum()), 2)

    def averaged(column):
        if not len(pr) or not pr[column].notna().any():
            return 0.0
        return round(float(pr[column].mean()), 2)

    tbs_a, tbs_b, tbs_s = summed("TbsAktual"), summed("TbsBudget"), summed("TbsSensus")
    jjg_a, jjg_b, jjg_s = int(summed("JanjangAktual")), int(summed("JanjangBudget")), int(summed("JanjangSensus"))
    eq(ctx, "tbs.aktual", tbs_a, info["tbs"]["aktual"], 0.011)
    eq(ctx, "tbs.budget", tbs_b, info["tbs"]["budget"], 0.011)
    eq(ctx, "tbs.sensus", tbs_s, info["tbs"]["sensus"], 0.011)
    eq(ctx, "jjg.aktual", jjg_a, info["jjg"]["aktual"], 0.5)
    eq(ctx, "jjg.budget", jjg_b, info["jjg"]["budget"], 1.01)
    eq(ctx, "jjg.sensus", jjg_s, info["jjg"]["sensus"], 1.01)
    eq(ctx, "bjr.aktual", averaged("BjrAktual"), info["bjr"]["aktual"], 0.0101)
    eq(ctx, "bjr.budget", averaged("BjrBudget"), info["bjr"]["budget"], 0.0101)
    eq(ctx, "bjr.sensus", averaged("BjrSensus"), info["bjr"]["sensus"], 0.0101)

    def yld(kg):
        return round(kg / 1000 / luas, 2) if luas else 0.0

    def gap(actual, target):
        if not target:
            return 0.0
        value = round((actual - target) / target * 100, 2)
        return 0.0 if value == 0 else value

    ya, yb, ys = yld(tbs_a), yld(tbs_b), yld(tbs_s)
    gb, gs = gap(ya, yb), gap(ya, ys)
    eq(ctx, "yield.aktual", ya, info["yield"]["aktual"], 0.0101)
    eq(ctx, "yield.budget", yb, info["yield"]["budget"], 0.0101)
    eq(ctx, "yield.sensus", ys, info["yield"]["sensus"], 0.0101)
    eq(ctx, "gap_act_bgt.value", gb, info["gap_act_bgt"]["value"], 0.0101)
    eq(ctx, "gap_act_sns.value", gs, info["gap_act_sns"]["value"], 0.0101)
    eq(ctx, "gap_act_bgt.kategori", cat(gb), info["gap_act_bgt"]["kategori"])
    eq(ctx, "gap_act_sns.kategori", cat(gs), info["gap_act_sns"]["kategori"])


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
