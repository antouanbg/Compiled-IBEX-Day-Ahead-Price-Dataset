# Simulation code: Individual and Coordinated MILP Dispatch of an Industrial PV-Battery Prosumer Community

Code accompanying the paper (Angelov, Trifonov, Pavlova, 2026) and the
Compiled IBEX Day-Ahead Price Dataset (DOI: 10.5281/zenodo.21191790).

## Contents
| File | Purpose |
|---|---|
| `build_inputs2.py` | Harmonizes IBEX prices (hourly + 15-min, BGN/EUR), builds PV model (Sofia / Stara Zagora) and industrial load archetypes -> `inputs2.csv` |
| `run_sim4.py` | Daily MILP dispatch (PuLP/CBC): 4 scenarios (independent/coordinated x cost-only/capacity-aware), contract pricing (DA - 2.15 EUR/MWh), endogenous curtailment, hybrid AC limit. Optional arg: import adder for sensitivity. |
| `sens_extra.py` | Sensitivities: P3 PV-only charging (no grid charging) and wheeling fee on internally shared energy |
| `run_qh.py` | 15-minute vs hourly resolution robustness (Jan-May 2026, LP relaxation) |
| `figs5.py` | All publication figures (600 dpi) |

## Requirements
Python 3.10+, `pandas`, `numpy`, `pulp`, `matplotlib`, `openpyxl` (CBC ships with PuLP).

## Reproduce
```bash
pip install pandas numpy pulp matplotlib openpyxl
python build_inputs2.py          # expects the dataset .xlsx alongside
python run_sim4.py sofia
python run_sim4.py sz
python run_sim4.py sofia 15 && python run_sim4.py sofia 45   # adder sensitivity
python sens_extra.py
python run_qh.py
python figs5.py
```
License: MIT for the code; the price data follow the dataset record.
