"""Reproduces Tables 2-5 of the manuscript from the simulation outputs."""
import json
S=json.load(open('kpis4_sofia.json')); Z=json.load(open('kpis4_sz.json'))
X=json.load(open('sens_extra.json'))
def eur(v): return f"{v:+,.0f}".replace("+","+" if v>=0 else "")
print("== Table 2: net annual cost & peak (Sofia) ==")
rows=[("Grid only (loads, no PV)",S['grid_only'],None),
      ("PV only (with curtailment)",S['pv_only']['cost'],S['pv_only']['peak']),
      ("PV+BESS independent (cost-only)",S['indiv']['cost'],S['indiv']['peak']),
      ("PV+BESS coordinated (cost-only)",S['coord']['cost'],S['coord']['peak']),
      ("PV+BESS independent (capacity-aware)",S['indiv_cap']['cost'],S['indiv_cap']['peak']),
      ("PV+BESS coordinated (capacity-aware)",S['coord_cap']['cost'],S['coord_cap']['peak'])]
for n,c,p in rows: print(f"{n:42s} {c:>10,.0f} EUR   peak {p if p else '-'}")
print("\n== Table 3: per-site, independent cost-only (Sofia) ==")
for k in ['P1','P2','P3']:
    print(f"{k}: PV-only {S['site_pv'][k]['cost']:>9,.0f}  PV+BESS {S['site_indiv'][k]['cost']:>10,.0f} EUR")
print("\n== Table 4: location comparison ==")
for lbl,d in [('Sofia',S),('Stara Zagora',Z)]:
    print(f"{lbl:14s} pv {d['pv_only']['cost']:>8,.0f}  coord {d['coord']['cost']:>9,.0f}  coord_cap {d['coord_cap']['cost']:>9,.0f}  SS {d['coord_cap']['ss']:.1f}%")
print("\n== Table 5: P3 retrofit by location ==")
for lbl,d,x in [('Sofia',S,X['p3_sofia']),('Stara Zagora',Z,X['p3_sz'])]:
    print(f"{lbl:14s} PV-only {d['site_pv']['P3']['cost']:>9,.0f}  PV+BESS {d['site_indiv']['P3']['cost']:>10,.0f}  (no grid charging: {x['no_grid']:,.0f})")
