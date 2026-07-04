import pandas as pd, numpy as np, pulp, json, time
FEE=30.0; ADM=2.15
# --- QH price series Jan-May 2026 (native EUR) ---
xl=pd.read_excel('/mnt/user-data/uploads/250929_Цени_Електроенергията_IBEX.xlsx', sheet_name=['2026'])
q=xl['2026']; q['Дата']=pd.to_datetime(q['Дата'],errors='coerce')
st=q['Период на доставка'].astype(str).str.split('-').str[0].str.strip()
hh=pd.to_datetime(st,format='%H:%M',errors='coerce')
q['ts']=q['Дата']+pd.to_timedelta(hh.dt.hour,'h')+pd.to_timedelta(hh.dt.minute,'m')
q['eur']=pd.to_numeric(q['Цена (EUR/MWh)'],errors='coerce')
s=q.dropna(subset=['ts','eur']).set_index('ts')['eur'].sort_index()
qidx=pd.date_range('2026-01-01','2026-05-31 23:45',freq='15min')
pq=s.reindex(qidx).interpolate(limit=8).ffill().bfill().values
# hourly comparator = mean of QH per hour (the averaging under test)
hidx=pd.date_range('2026-01-01','2026-05-31 23:00',freq='1h')
ph=pd.Series(pq,index=qidx).resample('1h').mean().reindex(hidx).values
# --- PV at both resolutions (Sofia), same physical model ---
def pv_model(idx):
    lat=np.radians(42.6977); tilt=np.radians(35.0); PR=0.82
    n=idx.dayofyear.values; hour=idx.hour.values+idx.minute.values/60.0+ (0.5 if (idx.freqstr or '').startswith('h') else 0.125)
    decl=np.radians(23.45*np.sin(np.radians(360*(284+n)/365.0)))
    Hh=np.radians(15.0*(hour-12.0)); Gon=1367*(1+0.033*np.cos(np.radians(360*n/365.0)))
    ci=np.sin(decl)*np.sin(lat-tilt)+np.cos(decl)*np.cos(lat-tilt)*np.cos(Hh)
    cz=np.sin(lat)*np.sin(decl)+np.cos(lat)*np.cos(decl)*np.cos(Hh)
    poa=np.clip(np.where(cz>0,Gon*0.70,0.0)*np.where(ci>0,ci,0.0),0,None)
    ktm={1:.42,2:.46,3:.52,4:.55,5:.58,6:.62,7:.65,8:.64,9:.60,10:.52,11:.42,12:.38}
    kt=np.array([ktm[m] for m in idx.month])
    return pd.Series((poa/1000.0)*PR*kt,index=idx)
pvh=pv_model(hidx); pvq=pv_model(qidx)
pvq*= pvh.sum()/ (pvq.sum()*0.25) *0.25 / 0.25  # align window energy
pvq*= (pvh.sum())/(pvq.mean()*len(pvq)*0.25/1.0) if False else 1.0
# simpler: scale QH so window energy equals hourly window energy
pvq = pvq * (pvh.sum() / (pvq.sum()*0.25))
CAL=1.185
pvh*=CAL; pvq*=CAL
# loads
hofd_h=hidx.hour.values; wk_h=hidx.dayofweek.values>=5
hofd_q=qidx.hour.values+qidx.minute.values/60.0; wk_q=qidx.dayofweek.values>=5
def shapes(h,wk):
    s1=(0.25+0.75*np.clip(np.sin(np.pi*(h-6)/12.0),0,None))*np.where(wk,0.4,1.0)
    s2=(0.85+0.15*np.cos(np.pi*(h-15)/12.0))*np.where(wk,0.92,1.0)
    return s1,s2
s1h,s2h=shapes(hofd_h,wk_h); s1q,s2q=shapes(hofd_q,wk_q)
# scale to same annual energies as main model (160/120 MWh/yr -> pro-rata window via same shape normalization on full year)
full=pd.date_range('2025-06-06','2026-06-05 23:00',freq='1h')
sf1,sf2=shapes(full.hour.values,full.dayofweek.values>=5)
k1=160e3/sf1.sum(); k2=120e3/sf2.sum()
L1h,L2h=s1h*k1,s2h*k2; L1q,L2q=s1q*k1,s2q*k2   # kW
P={ 'P1':dict(inv=50,cap=112.5,pbat=50,eta=0.95,smin=.10,hyb=True),
    'P2':dict(inv=30,cap=112.5,pbat=30,eta=0.95,smin=.10,hyb=True),
    'P3':dict(inv=98.56,cap=261.24,pbat=125,eta=0.89,smin=.05,hyb=False)}
def make(res):
    if res=='h': price=ph; H=24; dt=1.0
    else: price=pq; H=96; dt=0.25
    ip=price+FEE; ep=price-ADM
    data={}
    for k,v in P.items():
        kwp={'P1':80,'P2':48,'P3':98.56}[k]
        pv=(pvh if res=='h' else pvq).values*kwp
        pv=np.minimum(pv,v['inv'])
        ld={'P1':L1h if res=='h' else L1q,'P2':L2h if res=='h' else L2q,'P3':np.zeros(len(pv))}[k]
        data[k]=dict(pv=pv,ld=ld,**v,ec=np.sqrt(v['eta']),ed=np.sqrt(v['eta']))
    return ip,ep,H,dt,data
def solve(res,mode):
    ip,ep,H,dt,D=make(res); N=len(ip); days=N//H
    soc={k:0.5*D[k]['cap'] for k in D}; tot=0.0; pos=0
    for _ in range(days):
        sl=slice(pos,pos+H)
        m=pulp.LpProblem('x',pulp.LpMinimize); nets=[]; lasts={}
        GI=[pulp.LpVariable(f'GI{t}',0,None) for t in range(H)] if mode=='coord' else None
        GE=[pulp.LpVariable(f'GE{t}',0,None) for t in range(H)] if mode=='coord' else None
        obj=0
        for k,v in D.items():
            pv=v['pv'][sl]; ld=v['ld'][sl]
            gi=[pulp.LpVariable(f'gi{k}{t}',0,v['inv']+v['pbat']) for t in range(H)]
            ge=[pulp.LpVariable(f'ge{k}{t}',0,v['inv']) for t in range(H)]
            ch=[pulp.LpVariable(f'ch{k}{t}',0,v['pbat']) for t in range(H)]
            di=[pulp.LpVariable(f'di{k}{t}',0,v['pbat']) for t in range(H)]
            gp=[pulp.LpVariable(f'gp{k}{t}',0,float(pv[t])) for t in range(H)]
            so=[pulp.LpVariable(f's{k}{t}',v['smin']*v['cap'],v['cap']) for t in range(H)]
            for t in range(H):
                prev=soc[k] if t==0 else so[t-1]
                m+=so[t]==prev+ch[t]*v['ec']*dt-di[t]*dt/v['ed']
                if v['hyb']: m+=gp[t]+di[t]<=v['inv']
                if mode=='indiv': m+=ld[t]+ch[t]+ge[t]==gp[t]+di[t]+gi[t]
            if mode=='indiv':
                obj+=pulp.lpSum((gi[t]*ip[sl][t]-ge[t]*ep[sl][t])*dt/1000 for t in range(H))
                v['_gi']=gi; v['_ge']=ge
            else:
                nets.append([ld[t]+ch[t]-gp[t]-di[t] for t in range(H)])
            lasts[k]=so
        if mode=='coord':
            for t in range(H): m+=GI[t]-GE[t]==pulp.lpSum(n[t] for n in nets)
            obj=pulp.lpSum((GI[t]*ip[sl][t]-GE[t]*ep[sl][t])*dt/1000 for t in range(H))
        obj=obj-pulp.lpSum(lasts[k][H-1] for k in D)*max(ip[sl].mean(),0)/1000
        m+=obj; m.solve(pulp.PULP_CBC_CMD(msg=0))
        if mode=='indiv':
            for k,v in D.items():
                tot+=sum((v['_gi'][t].value()*ip[sl][t]-v['_ge'][t].value()*ep[sl][t])*dt/1000 for t in range(H))
        else:
            tot+=sum((GI[t].value()*ip[sl][t]-GE[t].value()*ep[sl][t])*dt/1000 for t in range(H))
        soc={k:lasts[k][H-1].value() for k in D}; pos+=H
    return tot
res={}
t0=time.time()
for r in ['h','q']:
    for mode in ['indiv','coord']:
        c=solve(r,mode); res[f'{r}_{mode}']=c
        print(f'{r} {mode}: {c:.0f} EUR  ({time.time()-t0:.0f}s)')
json.dump(res,open('qh_robust.json','w'),indent=2)
di=res['q_indiv']-res['h_indiv']; dc=res['q_coord']-res['h_coord']
print('delta indiv %.0f (%.1f%%)  delta coord %.0f (%.1f%%)'%(di,100*di/abs(res['h_indiv']),dc,100*dc/abs(res['h_coord'])))
