import pandas as pd, numpy as np, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
kS=json.load(open('kpis4_sofia.json')); kZ=json.load(open('kpis4_sz.json'))
s=pd.read_csv('series4_sofia.csv',index_col=0,parse_dates=True)
inp=pd.read_csv('inputs2.csv',index_col=0,parse_dates=True)
plt.rcParams.update({'font.size':12,'axes.grid':True,'grid.alpha':.3,'axes.titlesize':12,'legend.fontsize':10})
DPI=600

fig,ax=plt.subplots(figsize=(6.8,3.9))
lab=['Grid only','PV only','PV+BESS\n(individual)','PV+BESS\n(coordinated)']
vals=[kS['grid_only'],kS['pv_only']['cost'],kS['indiv']['cost'],kS['coord']['cost']]
b=ax.bar(lab,vals,color=['#9aa0a6','#f4b400','#4285f4','#0f9d58'])
for r,v in zip(b,vals):
    ax.text(r.get_x()+r.get_width()/2,v+(900 if v>=0 else -2600),f'{v/1000:+.1f}k',ha='center',fontsize=11)
ax.axhline(0,color='k',lw=.8); ax.set_ylabel('Net annual energy cost (EUR)')
ax.set_ylim(min(vals)*1.55, max(vals)*1.15)
ax.set_title('Community net annual cost (Sofia); negative = net income')
plt.tight_layout(); plt.savefig('fig_cost_ladder.png',dpi=DPI); plt.close()

fig,ax=plt.subplots(figsize=(6.4,3.8))
m=['Self-consumption','Self-sufficiency']; x=np.arange(2); w=.28
for off,key,lbl,c in [(-w,'indiv','Individual','#4285f4'),(0,'coord','Coordinated','#0f9d58'),
                      (w,'coord_cap','Coordinated cap.-aware','#7b1fa2')]:
    v=[kS[key]['sc'],kS[key]['ss']]
    ax.bar(x+off,v,w,label=lbl,color=c)
    for i,a in enumerate(v): ax.text(i+off,a+1,f'{a:.0f}',ha='center',fontsize=10)
ax.set_xticks(x); ax.set_xticklabels(m); ax.set_ylabel('%'); ax.set_ylim(0,100)
ax.set_title('Effect of coordination and objective (Sofia)'); ax.legend()
plt.tight_layout(); plt.savefig('fig_coordination.png',dpi=DPI); plt.close()

wk=s.loc['2025-07-07':'2025-07-13']
fig,ax=plt.subplots(figsize=(8.4,4.9))
ax.plot(wk.index,wk['gi_coord'],label='Import – coordinated (cost-only)',color='#0f9d58',lw=1.4)
ax.plot(wk.index,wk['gi_coord_cap'],label='Import – coordinated (capacity-aware)',color='#7b1fa2',lw=1.4)
ax.fill_between(wk.index,0,-wk['ge_coord'],color='#f4b400',alpha=.45,label='Export (cost-only)')
ax.set_ylabel('Power (kW)')
ax2=ax.twinx(); ax2.plot(wk.index,wk['price'],color='#db4437',lw=1.1,ls='--',label='Day-ahead price')
ax2.set_ylabel('Price (EUR/MWh)')
ax.set_title('Representative summer week (Sofia): grid exchange vs day-ahead price')
l1,la1=ax.get_legend_handles_labels(); l2,la2=ax2.get_legend_handles_labels()
fig.legend(l1+l2,la1+la2,fontsize=10,loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(0.5,0.0))
fig.autofmt_xdate(rotation=30)
plt.tight_layout(); plt.subplots_adjust(bottom=0.34)
plt.savefig('fig_week.png',dpi=DPI); plt.close()

fig,ax=plt.subplots(figsize=(7.0,3.9))
lab=['PV only','Individual\n(cost-only)','Coordinated\n(cost-only)','Individual\n(cap.-aware)','Coordinated\n(cap.-aware)']
vals=[kS['pv_only']['peak'],kS['indiv']['peak'],kS['coord']['peak'],kS['indiv_cap']['peak'],kS['coord_cap']['peak']]
b=ax.bar(lab,vals,color=['#f4b400','#4285f4','#0f9d58','#90caf9','#7b1fa2'])
for r,v in zip(b,vals): ax.text(r.get_x()+r.get_width()/2,v+5,f'{v:.0f}',ha='center',fontsize=11)
ax.set_ylabel('Peak community grid import (kW)')
ax.set_ylim(0, max(vals)*1.15)
ax.set_title('Coincident grid peak by dispatch variant (Sofia)')
plt.tight_layout(); plt.savefig('fig_peak.png',dpi=DPI); plt.close()

pvav=(np.minimum(inp['pv_sofia']*80,50)+np.minimum(inp['pv_sofia']*48,30)+np.minimum(inp['pv_sofia']*98.56,98.56))
load_tot=inp[['load_P1','load_P2']].sum(axis=1)
mB=pd.DataFrame({'PV available':pvav,'Load':load_tot,
  'Import (coord)':s['gi_coord'],'Export (coord)':s['ge_coord']}).resample('MS').sum()/1000
fig,ax=plt.subplots(figsize=(8.0,4.0))
x=np.arange(len(mB)); w=.2
for i,(c,col) in enumerate(zip(mB.columns,['#f4b400','#9aa0a6','#db4437','#0f9d58'])):
    ax.bar(x+(i-1.5)*w,mB[c],w,label=c,color=col)
ax.set_xticks(x); ax.set_xticklabels([d.strftime('%b %y') for d in mB.index],rotation=45,fontsize=10)
ax.set_ylabel('Energy (MWh)'); ax.set_title('Monthly community energy balance (Sofia, coordinated cost-only)')
ax.legend(ncol=4,fontsize=9)
plt.tight_layout(); plt.savefig('fig_monthly.png',dpi=DPI); plt.close()

fig,axs=plt.subplots(1,2,figsize=(8.4,3.9))
scn=['indiv','coord','indiv_cap','coord_cap']; lab=['Indiv.','Coord.','Indiv.\ncap.','Coord.\ncap.']
x=np.arange(4); w=.36
axs[0].bar(x-w/2,[kS[s]['cost'] for s in scn],w,label='Sofia',color='#4285f4')
axs[0].bar(x+w/2,[kZ[s]['cost'] for s in scn],w,label='Stara Zagora',color='#e8710a')
axs[0].axhline(0,color='k',lw=.8)
axs[0].set_xticks(x); axs[0].set_xticklabels(lab,fontsize=10)
axs[0].set_ylabel('Net annual cost (EUR)'); axs[0].set_title('(a) Net cost (negative = income)')
axs[0].legend(fontsize=9)
axs[1].bar(x-w/2,[kS[s]['ss'] for s in scn],w,label='Sofia',color='#4285f4')
axs[1].bar(x+w/2,[kZ[s]['ss'] for s in scn],w,label='Stara Zagora',color='#e8710a')
axs[1].set_xticks(x); axs[1].set_xticklabels(lab,fontsize=10)
axs[1].set_ylabel('Self-sufficiency (%)'); axs[1].set_title('(b) Self-sufficiency')
axs[1].legend(fontsize=9)
plt.tight_layout(); plt.savefig('fig_location.png',dpi=DPI); plt.close()
print('600dpi figures done')
