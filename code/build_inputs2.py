import pandas as pd, numpy as np
SRC='/mnt/user-data/uploads/250929_Цени_Електроенергията_IBEX.xlsx'
xl=pd.read_excel(SRC, sheet_name=None)
d=xl['2025'].copy(); d.columns=d.iloc[0]; d=d.iloc[1:].reset_index(drop=True)
d=d.rename(columns={d.columns[1]:'Date',d.columns[2]:'Hour'})
d['Date']=pd.to_datetime(d['Date'],errors='coerce'); d['Hour']=pd.to_numeric(d['Hour'],errors='coerce')
d['eur']=pd.to_numeric(d['Price (EUR)'],errors='coerce'); d=d.dropna(subset=['Date','Hour','eur'])
d['ts']=d['Date']+pd.to_timedelta(d['Hour']-1,unit='h')
s25=d.set_index('ts')['eur'].sort_index(); s25=s25[~s25.index.duplicated()]
q=xl['2026'].copy(); q['Дата']=pd.to_datetime(q['Дата'],errors='coerce')
st=q['Период на доставка'].astype(str).str.split('-').str[0].str.strip()
hh=pd.to_datetime(st,format='%H:%M',errors='coerce')
q['ts']=q['Дата']+pd.to_timedelta(hh.dt.hour,unit='h')+pd.to_timedelta(hh.dt.minute,unit='m')
q['eur']=pd.to_numeric(q['Цена (EUR/MWh)'],errors='coerce'); q=q.dropna(subset=['ts','eur'])
s26=q.set_index('ts')['eur'].sort_index().resample('1h').mean()
price=pd.concat([s25,s26]); price=price[~price.index.duplicated()].sort_index()
end=price.index.max().normalize()+pd.Timedelta(hours=23)
idx=pd.date_range((end+pd.Timedelta(hours=1))-pd.DateOffset(years=1),end,freq='1h')
price=price.reindex(idx).interpolate(limit=6).ffill().bfill(); price.name='price'

def pv_model(lat_deg, target_yield):
    lat=np.radians(lat_deg); tilt=np.radians(35.0); PR=0.82
    n=idx.dayofyear.values; hour=idx.hour.values+0.5
    decl=np.radians(23.45*np.sin(np.radians(360*(284+n)/365.0)))
    Hh=np.radians(15.0*(hour-12.0))
    Gon=1367*(1+0.033*np.cos(np.radians(360*n/365.0))); tau=0.70
    ci=np.sin(decl)*np.sin(lat-tilt)+np.cos(decl)*np.cos(lat-tilt)*np.cos(Hh)
    cz=np.sin(lat)*np.sin(decl)+np.cos(lat)*np.cos(decl)*np.cos(Hh)
    poa=np.clip(np.where(cz>0,Gon*tau,0.0)*np.where(ci>0,ci,0.0),0,None)
    ktm={1:.42,2:.46,3:.52,4:.55,5:.58,6:.62,7:.65,8:.64,9:.60,10:.52,11:.42,12:.38}
    kt=np.array([ktm[m] for m in idx.month])
    raw=pd.Series((poa/1000.0)*PR*kt,index=idx).clip(lower=0)
    return raw*(target_yield/raw.sum())

pv_sofia=pv_model(42.6977,1300.0)   # Sofia, PVGIS-class
pv_sz  =pv_model(42.4258,1390.0)    # Stara Zagora, sunnier southern BG

hofd=idx.hour.values; wknd=idx.dayofweek.values>=5
sh1=0.25+0.75*np.clip(np.sin(np.pi*(hofd-6)/12.0),0,None)
sh2=0.85+0.15*np.cos(np.pi*(hofd-15)/12.0)
sh3=0.2+0.8*np.clip(np.sin(np.pi*(hofd-7)/12.0),0,None)
prof={'P1':pd.Series(sh1*np.where(wknd,0.4,1.0),index=idx),
      'P2':pd.Series(sh2*np.where(wknd,0.92,1.0),index=idx),
      'P3':pd.Series(sh3*np.where(wknd,0.3,1.0),index=idx)}
annual={'P1':160.0,'P2':120.0,'P3':320.0}   # MWh/yr — producers that consume AND sell
load=pd.DataFrame(index=idx)
for k in prof: load[k]=prof[k]/prof[k].sum()*annual[k]*1000.0
inp=pd.DataFrame({'price':price,'pv_sofia':pv_sofia,'pv_sz':pv_sz}).join(load.add_prefix('load_'))
inp.to_csv('inputs2.csv')
for k in annual: print(k,'load=%.0f MWh peak=%.0f kW'%(load[k].sum()/1000,load[k].max()))
print('yield Sofia=%.0f SZ=%.0f kWh/kWp; price mean=%.2f'%(pv_sofia.sum(),pv_sz.sum(),price.mean()))
