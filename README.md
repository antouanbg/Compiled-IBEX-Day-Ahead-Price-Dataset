# Compiled IBEX Day-Ahead Price Dataset

Day-ahead electricity market prices for Bulgaria, compiled from the public market results of the
**Independent Bulgarian Energy Exchange (IBEX / БНЕБ)** — https://www.ibex.bg — covering
**January 2022 to June 2026** in a single Excel workbook.

The dataset accompanies the paper:

> Angelov, A.H.; Trifonov, R.; Pavlova, G. *Individual and Coordinated MILP Dispatch of an
> Industrial PV–Battery Prosumer Community on the Bulgarian Day-Ahead Market.* (submitted, 2026)

**File:** `250929_Цени_Електроенергията_IBEX.xlsx`

## Important market context

- On **1 October 2025** the Bulgarian day-ahead market moved from **hourly** to **15-minute**
  settlement periods. Sheets before that date are hourly; later data are quarter-hourly.
- BGN prices convert to EUR at the **fixed peg 1 EUR = 1.95583 BGN**.
- **Negative prices are real** and increasingly frequent (191 negative hours in the trailing
  twelve months ending 5 June 2026).
- Days with a **daylight-saving change have 23 or 25 delivery periods** — do not assume 24 hours
  per day.

## Sheet reference

| Sheet | Period | Resolution | Currency | Columns |
|---|---|---|---|---|
| `2022` | full year 2022 | hourly | EUR + BGN | `Date`, `Hour` (1–24), `Price (EUR)`, `Price (BGN)`, `Volume` |
| `2023` | full year 2023 | hourly | EUR + BGN | same as above |
| `2024` | full year 2024 | hourly | EUR + BGN | same as above |
| `2025` | full year 2025 | hourly | EUR + BGN | same as above, **but the header row is embedded in the first data row** (see parsing note) |
| `2025_okt` | 1 Oct – 31 Dec 2025 | 15-minute | **BGN** | `Дата` (date), `Продукт`, `Период на доставка` (delivery period, e.g. `13:00 - 13:15`), `Цена (BGN/MWh)`, `Общо Количество (MW)` |
| `2026` | 1 Jan – 5 Jun 2026 | 15-minute | EUR | `Дата`, `Продукт`, `Период на доставка`, `Цена (EUR/MWh)`, `Общо Количество (MW)` |

Notes:
- `Hour` in the hourly sheets is the delivery hour numbered **1–24** (hour *h* covers
  *(h−1):00 – h:00* local time).
- `2025_okt` **overlaps** the hourly `2025` sheet for Q4 2025 — it is the same market period at
  15-minute resolution in BGN. Use one or the other, not both.

## Parsing notes (pandas)

```python
import pandas as pd
xl = pd.read_excel("250929_Цени_Електроенергията_IBEX.xlsx", sheet_name=None)

# Hourly sheets 2022–2024: read directly
d24 = xl["2024"]                      # Date, Hour, Price (EUR), Price (BGN), Volume

# Sheet "2025": header is embedded in row 0
d25 = xl["2025"]
d25.columns = d25.iloc[0]
d25 = d25.iloc[1:].reset_index(drop=True)

# Quarter-hourly sheets: parse delivery-period start, resample to hourly if needed
q = xl["2026"]
start = q["Период на доставка"].astype(str).str.split("-").str[0].str.strip()
t = pd.to_datetime(start, format="%H:%M")
q["ts"] = pd.to_datetime(q["Дата"]) + pd.to_timedelta(t.dt.hour, "h") \
                                    + pd.to_timedelta(t.dt.minute, "m")
hourly = q.set_index("ts")["Цена (EUR/MWh)"].resample("1h").mean()

# BGN -> EUR (sheet "2025_okt")
EUR = 1.95583
```

## Source and licence

Raw market results are published by IBEX (БНЕБ ЕАД) at https://www.ibex.bg. This repository
provides a compiled, research-ready copy; all underlying market data remain the property of
their publisher. Compilation released under **CC BY 4.0** — please cite as below.

## Cite as

```bibtex
@misc{angelov2026ibexdataset,
  author = {Angelov, Antouan H.},
  title  = {Compiled IBEX Day-Ahead Price Dataset (hourly and 15-minute
            IBEX day-ahead market publications, 2022--2026)},
  year   = {2026},
  url    = {https://github.com/antouanbg/Compiled-IBEX-Day-Ahead-Price-Dataset}
}
```
