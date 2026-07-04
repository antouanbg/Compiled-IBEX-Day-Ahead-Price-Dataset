import pandas as pd, numpy as np, pulp, json, sys
LOC=sys.argv[1]
FEE_ARG=float(sys.argv[2]) if len(sys.argv)>2 else None
import time
SOLVE_STATS={'n':0,'t':0.0,'tmax':0.0,'vars':0,'bins':0,'cons':0}
def timed_solve(m):
    t0=time.time(); m.solve(pulp.PULP_CBC_CMD(msg=0)); dt=time.time()-t0
    SOLVE_STATS['n']+=1; SOLVE_STATS['t']+=dt; SOLVE_STATS['tmax']=max(SOLVE_STATS['tmax'],dt)
    if SOLVE_STATS['vars']==0:
        vs=m.variables(); SOLVE_STATS['vars']=len(vs)
        SOLVE_STATS['bins']=sum(1 for v in vs if v.cat=='Integer' or v.cat=='Binary')
        SOLVE_STATS['cons']=len(m.constraints)
inp=pd.read_csv('inputs2.csv', index_col=0, parse_dates=True)
idx=inp.index; price=inp['price'].values
FEE_IMP=30.0; ADM_FEE=2.15; C_PEAK=0.35
if FEE_ARG is not None: FEE_IMP=FEE_ARG
imp_p=price+FEE_IMP
exp_p=price-ADM_FEE          # ENERGO-PRO contract: DA price minus admin fee; negative => producer pays
pvk=inp['pv_sofia' if LOC=='sofia' else 'pv_sz'].values
# P1: STE-50HT-150 + STE-112A-DC (80 kWp); P2: STE-30HT-150 + STE-112A-DC (48 kWp)
# P3: real 98.56 kWp merchant PV plant (own inverter) + STE-261L-125P retrofit, no on-site load
P={'P1':dict(kwp=80,   inv=50,   cap=112.5, pbat=50,  eta=0.95, socmin=0.10, socmax=1.00, hybrid=True,  load=inp['load_P1'].values),
   'P2':dict(kwp=48,   inv=30,   cap=112.5, pbat=30,  eta=0.95, socmin=0.10, socmax=1.00, hybrid=True,  load=inp['load_P2'].values),
   'P3':dict(kwp=98.56,inv=98.56,cap=261.24,pbat=125, eta=0.89, socmin=0.05, socmax=1.00, hybrid=False, load=np.zeros(len(idx)))}
for k,v in P.items():
    v['pvav']=np.minimum(pvk*v['kwp'],v['inv'])           # available PV after inverter clip
    v['gexp_lim']=v['inv']                                # export capped by connection ~ inverter/installed
    v['gimp_lim']=v['inv']+v['pbat']   # import connection cap: AC rating + battery charging power
    v['ec']=np.sqrt(v['eta']); v['ed']=np.sqrt(v['eta']); v['soc0']=0.5*v['cap']
H=24; N=len(idx)

def add_site(m,k,v,sl,s0):
    pvav=v['pvav'][sl]
    ch=[pulp.LpVariable(f'ch_{k}_{t}',0,v['pbat']) for t in range(H)]
    di=[pulp.LpVariable(f'di_{k}_{t}',0,v['pbat']) for t in range(H)]
    gp=[pulp.LpVariable(f'gp_{k}_{t}',0,float(pvav[t])) for t in range(H)]   # dispatched PV (curtailment allowed)
    y =[pulp.LpVariable(f'y_{k}_{t}',cat='Binary') for t in range(H)]
    so=[pulp.LpVariable(f's_{k}_{t}',v['socmin']*v['cap'],v['socmax']*v['cap']) for t in range(H)]
    for t in range(H):
        prev=s0 if t==0 else so[t-1]
        m+=so[t]==prev+ch[t]*v['ec']-di[t]/v['ed']
        m+=ch[t]<=v['pbat']*y[t]; m+=di[t]<=v['pbat']*(1-y[t])
        if v.get('hybrid'): m+=gp[t]+di[t]<=v['inv']   # DC-coupled hybrid: joint AC output limit
    return ch,di,gp,so

def solve_indiv(v,k,sl,s0,cap):
    ld=v['load'][sl]; ip=imp_p[sl]; ep=exp_p[sl]
    m=pulp.LpProblem('d',pulp.LpMinimize)
    gi=[pulp.LpVariable(f'gi{t}',0,v['gimp_lim']) for t in range(H)]
    ge=[pulp.LpVariable(f'ge{t}',0,v['gexp_lim']) for t in range(H)]
    ch,di,gp,so=add_site(m,k,v,sl,s0)
    for t in range(H):
        m+=ld[t]+ch[t]+ge[t]==gp[t]+di[t]+gi[t]
    obj=pulp.lpSum(gi[t]*ip[t]/1000-ge[t]*ep[t]/1000 for t in range(H))-so[H-1]*max(ip.mean(),0)/1000
    if cap:
        pk=pulp.LpVariable('pk',0,None)
        for t in range(H): m+=pk>=gi[t]
        obj=obj+pk*C_PEAK
    m+=obj; timed_solve(m)
    GI=np.array([x.value() for x in gi]); GE=np.array([x.value() for x in ge])
    DI=np.array([x.value() for x in di]); GP=np.array([x.value() for x in gp])
    return GI,GE,DI,GP,so[H-1].value(),(GI*ip/1000-GE*ep/1000).sum()

def solve_coord(sl,s0,cap):
    m=pulp.LpProblem('c',pulp.LpMinimize); ip=imp_p[sl]; ep=exp_p[sl]
    Gi=[pulp.LpVariable(f'Gi{t}',0,None) for t in range(H)]
    Ge=[pulp.LpVariable(f'Ge{t}',0,sum(P[k]['gexp_lim'] for k in P)) for t in range(H)]
    parts={}; last={}
    for k,v in P.items():
        ch,di,gp,so=add_site(m,k,v,sl,s0[k])
        parts[k]=(ch,di,gp); last[k]=so
    for t in range(H):
        m+=Gi[t]-Ge[t]==pulp.lpSum(P[k]['load'][sl][t]+parts[k][0][t]-parts[k][2][t]-parts[k][1][t] for k in P)
    term=pulp.lpSum(last[k][H-1] for k in P)*max(ip.mean(),0)/1000
    obj=pulp.lpSum(Gi[t]*ip[t]/1000-Ge[t]*ep[t]/1000 for t in range(H))-term
    if cap:
        pk=pulp.LpVariable('pk',0,None)
        for t in range(H): m+=pk>=Gi[t]
        obj=obj+pk*C_PEAK
    m+=obj; timed_solve(m)
    GIv=np.array([x.value() for x in Gi]); GEv=np.array([x.value() for x in Ge])
    se={k:last[k][H-1].value() for k in P}
    dis={k:sum(x.value() for x in parts[k][1]) for k in P}
    cur={k:sum(P[k]['pvav'][sl][t]-parts[k][2][t].value() for t in range(H)) for k in P}
    return GIv,GEv,se,(GIv*ip/1000-GEv*ep/1000).sum(),dis,cur

SCENS=['indiv','coord'] if FEE_ARG is not None else ['indiv','coord','indiv_cap','coord_cap']
scen={s:dict(gi=np.zeros(N),ge=np.zeros(N),cost=0.0,di={k:0.0 for k in P},cur={k:0.0 for k in P})
      for s in SCENS}
soc={s:{k:P[k]['soc0'] for k in P} for s in scen}
site={k:dict(gi=np.zeros(N),ge=np.zeros(N),cost=0.0) for k in P}
pos=0
for day in np.unique(idx.normalize()):
    if pos+H>N: break
    sl=slice(pos,pos+H)
    for s,cap in [x for x in [('indiv',False),('indiv_cap',True)] if x[0] in SCENS]:
        for k,v in P.items():
            GI,GE,DI,GP,se,c=solve_indiv(v,k,sl,soc[s][k],cap)
            scen[s]['gi'][sl]+=GI; scen[s]['ge'][sl]+=GE; scen[s]['cost']+=c
            scen[s]['di'][k]+=DI.sum(); scen[s]['cur'][k]+=(v['pvav'][sl]-GP).sum(); soc[s][k]=se
            if s=='indiv': site[k]['gi'][sl]=GI; site[k]['ge'][sl]=GE; site[k]['cost']+=c
    for s,cap in [x for x in [('coord',False),('coord_cap',True)] if x[0] in SCENS]:
        GIv,GEv,se,c,dis,cur=solve_coord(sl,soc[s],cap)
        scen[s]['gi'][sl]=GIv; scen[s]['ge'][sl]=GEv; scen[s]['cost']+=c
        for k in P: scen[s]['di'][k]+=dis[k]; scen[s]['cur'][k]+=cur[k]
        soc[s]=se
    pos+=H

# baselines under contract pricing (with curtailment of negative-value export)
S_grid=sum((P[k]['load']*imp_p/1000).sum() for k in P)
gi_pv=np.zeros(N); S_pv=0; site_pv={}
for k,v in P.items():
    net=v['load']-v['pvav']
    im=np.clip(net,0,None)
    ex_raw=np.clip(-net,0,None)
    ex=np.where(exp_p>0,ex_raw,0.0)          # curtail exports when contract price <= 0
    c=(im*imp_p/1000-ex*exp_p/1000).sum(); S_pv+=c; gi_pv+=im
    site_pv[k]=dict(cost=c,gridonly=(v['load']*imp_p/1000).sum(),
                    pv_MWh=v['pvav'].sum()/1000,load_MWh=v['load'].sum()/1000,exp_MWh=ex.sum()/1000)
pv_gen=sum(P[k]['pvav'].sum() for k in P); load_tot=sum(P[k]['load'].sum() for k in P)
def kp(s):
    d=scen[s]
    return dict(cost=d['cost'],peak=float(d['gi'].max()),sc=100*(1-d['ge'].sum()/pv_gen),
                ss=100*(1-d['gi'].sum()/load_tot),cyc={k:d['di'][k]/P[k]['cap'] for k in P},
                cur_MWh=sum(d['cur'].values())/1000)
out=dict(loc=LOC,fee=FEE_IMP,solver=SOLVE_STATS,grid_only=S_grid,pv_only=dict(cost=S_pv,peak=float(gi_pv.max())),
         pv_MWh=pv_gen/1000,load_MWh=load_tot/1000,site_pv=site_pv,
         site_indiv={k:dict(cost=site[k]['cost'],peak=float(site[k]['gi'].max()),
                            exp_MWh=site[k]['ge'].sum()/1000) for k in P},
         **{s:kp(s) for s in scen})
tag=f'kpis4_{LOC}'+(f'_fee{int(FEE_IMP)}' if FEE_ARG is not None else '')
json.dump(out,open(tag+'.json','w'),indent=2,default=float)
if FEE_ARG is None:
 pd.DataFrame({'price':price,'gi_indiv':scen['indiv']['gi'],'gi_coord':scen['coord']['gi'],
  'gi_coord_cap':scen['coord_cap']['gi'],'ge_coord':scen['coord']['ge'],
  'ge_coord_cap':scen['coord_cap']['ge'],'ge_indiv':scen['indiv']['ge']},index=idx).to_csv(f'series4_{LOC}.csv')
print(LOC.upper(),'(contract pricing DA-2.15, curtailment enabled)')
print('%-11s %10s %7s %6s %6s %8s'%('scen','cost','peak','SC%','SS%','curtMWh'))
print('%-11s %10.0f'%('grid',S_grid)); print('%-11s %10.0f %7.0f'%('pv',S_pv,gi_pv.max()))
for s in SCENS:
    k=kp(s); print('%-11s %10.0f %7.0f %6.1f %6.1f %8.1f'%(s,k['cost'],k['peak'],k['sc'],k['ss'],k['cur_MWh']))
