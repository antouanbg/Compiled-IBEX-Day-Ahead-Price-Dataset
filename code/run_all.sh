#!/usr/bin/env bash
# Full reproduction pipeline. Requires the dataset .xlsx in the parent folder.
set -e
pip install -q pandas numpy pulp matplotlib openpyxl
python build_inputs2.py
python run_sim4.py sofia
python run_sim4.py sz
python run_sim4.py sofia 15
python run_sim4.py sofia 45
python sens_extra.py     # P3 grid-charging + wheeling sensitivities
python run_qh.py
python make_tables.py
python figs5.py
echo "All tables (2-5) and figures (1-6) reproduced."
