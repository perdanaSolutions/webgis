from common import *
x=load_prod(); print(x.shape)
x["period"]=pd.to_datetime(dict(year=x.Year,month=x.Month,day=1))
print("Year/Month counts:",x.groupby("Year").size().to_dict(), "| months",sorted(x.Month.unique()))
x["key"]=list(zip(x.UnitCode,x.DivisionCode,x.KodeBlok,x.Year,x.Month))
print("dup keys excel:",x.key.duplicated().sum())
d=x[x.key.duplicated(keep=False)].sort_values("key"); print(d[["key","TbsAktual","TbsBudget","JanjangAktual"]].head(6).to_string())
db=sql(f"""SELECT {BLK}, p.period, p.ffb_actual_kg,p.ffb_budget_kg,p.ffb_census_kg,p.bunches_actual,p.bunches_budget,p.bunches_census,p.bjr_actual,p.bjr_budget,p.bjr_census
 {BJ} JOIN trx.block_productions p ON p.block_id=bl.id""")
db["key"]=list(zip(db.est,db.dv,db.blk,db.period.map(lambda d:d.year),db.period.map(lambda d:d.month)))
print("DB rows",len(db),"dup:",db.key.duplicated().sum())
ek,dk=set(x.key),set(db.key)
print("excel not in db:",len(ek-dk),"db not in excel:",len(dk-ek))
miss=x[x.key.isin(ek-dk)]
print("missing by year/month:",miss.groupby(["Year","Month"]).size().head(24).to_dict())
print("missing by estate:",miss.groupby("UnitCode").size().to_dict())
print(miss[["key","TbsAktual","TbsBudget","JanjangAktual","LuasTanam"]].head(8).to_string())
print("db-not-in-excel sample:",list(dk-ek)[:5])
xx=x.drop_duplicates("key",keep="last")
m=xx.merge(db,on="key",suffixes=("_x","_d")); print("matched",len(m))
def cmp(n,a,b,tol=0.01):
    a=pd.to_numeric(a,errors="coerce"); b=pd.to_numeric(b,errors="coerce")
    bad=~((a-b).abs()<=tol)&~(a.isna()&b.isna())
    print(f"{n:14s} mismatch={int(bad.sum())}",m.loc[bad,["key"]].head(2).values.tolist() if bad.any() else "")
    return bad
cmp("TbsAktual",m.TbsAktual,m.ffb_actual_kg); cmp("TbsBudget",m.TbsBudget,m.ffb_budget_kg); cmp("TbsSensus",m.TbsSensus,m.ffb_census_kg)
cmp("JanjangAkt",m.JanjangAktual,m.bunches_actual,0.5); cmp("JanjangBgt",m.JanjangBudget,m.bunches_budget); cmp("JanjangSns",m.JanjangSensus,m.bunches_census)
cmp("BjrAktual",m.BjrAktual,m.bjr_actual,0.001); cmp("BjrBudget",m.BjrBudget,m.bjr_budget,0.001); cmp("BjrSensus",m.BjrSensus,m.bjr_census,0.001)
