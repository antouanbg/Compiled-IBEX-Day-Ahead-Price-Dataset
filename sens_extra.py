import pandas as pd, numpy as np, pulp, json
inp=pd.read_csv('inputs2.csv', index_col=0, parse_dates=True)
idx=inp.index; price=inp['price'].values; N=len(idx); H=24
FEE_IMP=30.0; ADM=2.15
imp_p=price+FEE_IMP; exp_p=price-ADM

def p3_params(loc):
    pvk=inp['pv_sofia' if loc=='sofia' else 'pv_sz'].values
    v=dict(cap=261.24,pbat=125,eta=0.89,socmin=0.05,socmax=1.0,inv=98.56)
    v['pvav']=np.minimum(pvk*98.56,98.56); v['ec']=v['ed']=np.sqrt(v['eta']); v['soc0']=0.5*v['cap']
    return v

def run_p3(loc, grid_charge):
    v=p3_params(loc); soc=v['soc0']; total=0.0; pos=0
    for _ in range(365):
        sl=slice(pos,pos+H); pv=v['pvav'][sl]; ip=imp_p[sl]; ep=exp_p[sl]
        m=pulp.LpProblem('p',pulp.LpMinimize)
        gi=[pulp.LpVariable(f'gi{t}',0,v['inv']+v['pbat']) for t in range(H)]
        ge=[pulp.LpVariable(f'ge{t}',0,v['inv']) for t in range(H)]
        ch=[pulp.LpVariable(f'ch{t}',0,v['pbat']) for t in range(H)]
        di=[pulp.LpVariable(f'di{t}',0,v['pbat']) for t in range(H)]
        gp=[pulp.LpVariable(f'gp{t}',0,float(pv[t])) for t in range(H)]
        y=[pulp.LpVariable(f'y{t}',cat='Binary') for t in range(H)]
        so=[pulp.LpVariable(f's{t}',v['socmin']*v['cap'],v['socmax']*v['cap']) for t in range(H)]
        for t in range(H):
            prev=soc if t==0 else so[t-1]
            m+=so[t]==prev+ch[t]*v['ec']-di[t]/v['ed']
            m+=ch[t]+ge[t]==gp[t]+di[t]+gi[t]
            m+=ch[t]<=v['pbat']*y[t]; m+=di[t]<=v['pbat']*(1-y[t])
            if not grid_charge: m+=ch[t]<=gp[t]        # PV-only charging
        m+=pulp.lpSum(gi[t]*ip[t]/1000-ge[t]*ep[t]/1000 for t in range(H))-so[H-1]*max(ip.mean(),0)/1000
        m.solve(pulp.PULP_CBC_CMD(msg=0))
        total+=sum((gi[t].value()*ip[t]-ge[t].value()*ep[t])/1000 for t in range(H))
        soc=so[H-1].value(); pos+=H
    return total

P_ALL={'P1':dict(kwp=80,inv=50,cap=112.5,pbat=50,eta=0.95,socmin=0.10,socmax=1.0,hybrid=True,load=inp['load_P1'].values),
       'P2':dict(kwp=48,inv=30,cap=112.5,pbat=30,eta=0.95,socmin=0.10,socmax=1.0,hybrid=True,load=inp['load_P2'].values),
       'P3':dict(kwp=98.56,inv=98.56,cap=261.24,pbat=125,eta=0.89,socmin=0.05,socmax=1.0,hybrid=False,load=np.zeros(N))}
pvk=inp['pv_sofia'].values
for k,v in P_ALL.items():
    v['pvav']=np.minimum(pvk*v['kwp'],v['inv']); v['ec']=v['ed']=np.sqrt(v['eta']); v['soc0']=0.5*v['cap']
    v['gexp']=v['inv']; v['gimp']=v['inv']+v['pbat']

def run_coord_wheel(w):
    soc={k:P_ALL[k]['soc0'] for k in P_ALL}; total=0.0; wheel_paid=0.0; pos=0
    for _ in range(365):
        sl=slice(pos,pos+H); ip=imp_p[sl]; ep=exp_p[sl]
        m=pulp.LpProblem('c',pulp.LpMinimize)
        Gi=[pulp.LpVariable(f'Gi{t}',0,None) for t in range(H)]
        Ge=[pulp.LpVariable(f'Ge{t}',0,None) for t in range(H)]
        net={}; last={}; apos={}
        for k,v in P_ALL.items():
            pv=v['pvav'][sl]; ld=v['load'][sl]
            ch=[pulp.LpVariable(f'ch{k}{t}',0,v['pbat']) for t in range(H)]
            di=[pulp.LpVariable(f'di{k}{t}',0,v['pbat']) for t in range(H)]
            gp=[pulp.LpVariable(f'gp{k}{t}',0,float(pv[t])) for t in range(H)]
            y=[pulp.LpVariable(f'y{k}{t}',cat='Binary') for t in range(H)]
            so=[pulp.LpVariable(f's{k}{t}',v['socmin']*v['cap'],v['socmax']*v['cap']) for t in range(H)]
            a=[pulp.LpVariable(f'a{k}{t}',0,None) for t in range(H)]   # positive part of site net position
            for t in range(H):
                prev=soc[k] if t==0 else so[t-1]
                m+=so[t]==prev+ch[t]*v['ec']-di[t]/v['ed']
                m+=ch[t]<=v['pbat']*y[t]; m+=di[t]<=v['pbat']*(1-y[t])
                if v['hybrid']: m+=gp[t]+di[t]<=v['inv']
                m+=a[t]>= ld[t]+ch[t]-gp[t]-di[t]
            net[k]=[ld[t]+ch[t]-gp[t]-di[t] for t in range(H)]; last[k]=so; apos[k]=a
        for t in range(H): m+=Gi[t]-Ge[t]==pulp.lpSum(net[k][t] for k in P_ALL)
        shared=[pulp.lpSum(apos[k][t] for k in P_ALL)-Gi[t] for t in range(H)]  # internally shared energy
        term=pulp.lpSum(last[k][H-1] for k in P_ALL)*max(ip.mean(),0)/1000
        m+=pulp.lpSum(Gi[t]*ip[t]/1000-Ge[t]*ep[t]/1000+shared[t]*w/1000 for t in range(H))-term
        m.solve(pulp.PULP_CBC_CMD(msg=0))
        total+=sum((Gi[t].value()*ip[t]-Ge[t].value()*ep[t])/1000 for t in range(H))
        wheel_paid+=sum(max(sum(apos[k][t].value() for k in P_ALL)-Gi[t].value(),0)*w/1000 for t in range(H))
        soc={k:last[k][H-1].value() for k in P_ALL}; pos+=H
    return total, wheel_paid

out={}
for loc in ['sofia','sz']:
    gc=run_p3(loc,True); ng=run_p3(loc,False)
    out[f'p3_{loc}']=dict(grid_charge=gc,no_grid=ng)
    print(f'P3 {loc}: grid-charging {gc:.0f}  PV-only-charging {ng:.0f}  delta {ng-gc:.0f}')
for w in [10.0,20.0]:
    tc,wp=run_coord_wheel(w)
    out[f'wheel_{int(w)}']=dict(energy=tc,wheeling=wp,total=tc+wp)
    print(f'wheeling w={w:.0f}: energy {tc:.0f}  wheeling paid {wp:.0f}  total {tc+wp:.0f}')
json.dump(out,open('sens_extra.json','w'),indent=2,default=float)
