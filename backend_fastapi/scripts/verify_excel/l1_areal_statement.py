from common import *
x=load_stmt(); print(x.shape); print(x.dtypes.to_string())
print("Year/Month:",x.groupby(["Year","Month"]).size().to_dict())
x["key"]=list(zip(x.UnitCode,x.DivisionCode,x.KodeBlok,x.Year,x.Month))
print("dup keys excel:",x.key.duplicated().sum())
db=sql(f"""SELECT {BLK}, a.period, ps.code status, a.planting_year, a.planting_month, a.planted_area_ha, a.land_area_ha, a.tree_count, a.sph,
 a.pct_flat,a.pct_hilly,a.pct_undulating,a.pct_steep, so.name soil, tp.name topo, bt.name btype, a.area_id
 {BJ} JOIN trx.area_statements a ON a.block_id=bl.id
 LEFT JOIN ref.planting_statuses ps ON ps.id=a.planting_status_id LEFT JOIN ref.soil_types so ON so.id=a.soil_type_id
 LEFT JOIN ref.topography_types tp ON tp.id=a.topography_type_id LEFT JOIN ref.block_types bt ON bt.id=bl.block_type_id""")
db["key"]=list(zip(db.est,db.dv,db.blk,db.period.map(lambda d:d.year),db.period.map(lambda d:d.month)))
print("DB rows",len(db),"dup keys db:",db.key.duplicated().sum())
ek,dk=set(x.key),set(db.key)
print("excel not in db:",len(ek-dk),"db not in excel:",len(dk-ek), "e.g.",list(ek-dk)[:3],list(dk-ek)[:3])
m=x.merge(db,on="key",suffixes=("_x","_d"))
print("matched",len(m))
def cmp(name,a,b,tol=0.0051):
    a=pd.to_numeric(a,errors="coerce"); b=pd.to_numeric(b,errors="coerce")
    bad=~((a-b).abs()<=tol) & ~(a.isna()&b.isna())
    print(f"{name:14s} mismatch={int(bad.sum())}", m.loc[bad,["key"]].head(2).values.tolist() if bad.any() else "")
cmp("LuasTanam",m.LuasTanam,m.planted_area_ha); cmp("LuasTanah",m.LuasTanah,m.land_area_ha)
cmp("TotalPokok",m.TotalPokok,m.tree_count,0.5); cmp("SPH",m.SPH,m.sph)
cmp("TanahDatar",m.TanahDatar,m.pct_flat,0.5); cmp("Berbukit",m.Berbukit,m.pct_hilly,0.5)
cmp("Gelombang",m.Gelombang,m.pct_undulating,0.5); cmp("Curam",m.Curam,m.pct_steep,0.5)
cmp("TahunTanam",m.TahunTanam,m.planting_year,0.5)
cmp("BulanTanam",m.BulanTanam.astype(str).str.strip().str.capitalize().map({**MON,"Mei":5,"Agu":8,"Okt":10,"Des":12}),m.planting_month,0.5)
for n,a,b in [("StatusTanam","StatusTanam","status"),("Topografi","JenisTopografi","topo"),("Tanah","JenisTanah","soil"),("TipeBlok","TipeBlok","btype")]:
    bad=m[a].astype(str).str.strip().str.upper()!=m[b].astype(str).str.strip().str.upper()
    print(f"{n:14s} mismatch={int(bad.sum())}", m.loc[bad,[a,b]].drop_duplicates().head(4).values.tolist())
