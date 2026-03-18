# IRRBB Model — Basel III / BCBS 368

[![CI](https://github.com/marieltv/IRRBB_model/actions/workflows/ci.yaml/badge.svg)](https://github.com/marieltv/IRRBB_model/actions)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Python implementation of the **Interest Rate Risk in the Banking Book (IRRBB)** standardised framework prescribed by the Basel Committee on Banking Supervision in **BCBS 368 (April 2016)**.

The model computes **ΔEVE** (Economic Value of Equity sensitivity) and **ΔNII** (Net Interest Income sensitivity) across all six prescribed shock scenarios, detects supervisory outlier breaches, and provides a full interactive dashboard via Streamlit.

---

## Features

- **19 BCBS 368 time buckets** — exact repricing bands from *Annex 2, Table 2*; no manual bucket assignment
- **Full cash flow schedule per instrument** — bullet (fixed/floating), amortising, and demand deposits; 500+ scheduled cash flows on the default balance sheet
- **Proper EVE discounting** — cash flows discounted at a yield curve shocked per bucket, not a duration approximation
- **Bond convexity correctly captured** — parallel down produces larger |ΔEVE| than parallel up
- **Shock interpolation** — linear interpolation from 6 BCBS reference tenors to all 19 bucket midpoints
- **Outlier detection** — |ΔEVE| > 15% of Tier 1 Capital flags a supervisory outlier per BCBS 368 §99
- **Streamlit dashboard** — scenario selector, EVE waterfall, repricing gap, yield curve
- **43 unit tests** — covering time buckets, cash flow mechanics, yield curve, NII/EVE calculations, and outlier logic
- **GitHub Actions CI** — runs tests on Python 3.10/3.11/3.12, lint check, model smoke test

---

## Project Structure

```
irrbb-model/
├── src/
│   ├── time_buckets.py    # 19 BCBS 368 repricing time bands + years_to_bucket()
│   ├── cashflows.py       # Instrument class: bullet_fixed, bullet_floating,
│   │                      #   amortising, demand_deposit — full CF schedule
│   ├── yield_curve.py     # Base curve + shocked curve discounting
│   ├── balance_sheet.py   # Hypothetical bank balance sheet (10 assets, 10 liabilities)
│   ├── scenarios.py       # 6 BCBS 368 shock scenarios with interpolation
│   ├── calculator.py      # IRRBBCalculator: NII, EVE, gap, attribution
│   └── plots.py           # Matplotlib charts for static output
├── tests/
│   └── test_irrbb.py      # 43 unit tests (pytest)
├── app.py                 # Streamlit dashboard
├── main.py                # CLI entry point
├── requirements.txt
└── .github/
    └── workflows/
        └── ci.yml         # GitHub Actions: test + lint + smoke test
```

---

## Methodology

### EVE Calculation

For each instrument, cash flows are generated at their contractual payment dates and slotted into the correct BCBS 368 bucket. EVE sensitivity is computed by discounting those cash flows at the base curve and again at the shocked curve:

```
PV_base(i)    = Σ_k  CF_i[k] × DF_base[k]
PV_shocked(i) = Σ_k  CF_i[k] × DF_shocked[k]

ΔEVE = Σ_assets [PV_shocked - PV_base]  -  Σ_liabilities [PV_shocked - PV_base]
```

where `DF[k] = 1 / (1 + r[k])^t_k` and `t_k` is the bucket midpoint in years.

### NII Calculation

NII is computed over a 1-year horizon. Only floating-rate instruments (bullet_floating, demand_deposit) contribute — their notional reprices at the rate shock applicable to their repricing bucket:

```
ΔNII = Σ_floating_assets    notional_i × shock_bp(bucket_i) / 10,000
     - Σ_floating_liabilities notional_i × shock_bp(bucket_i) / 10,000
```

### Shock Scenarios (BCBS 368, Annex 2)

| Scenario | Description | O/N | 1Y | 2Y | 5Y | 10Y | 20Y |
|---|---|---|---|---|---|---|---|
| Parallel Up | Uniform +200bp | +200 | +200 | +200 | +200 | +200 | +200 |
| Parallel Down | Uniform −200bp | −200 | −200 | −200 | −200 | −200 | −200 |
| Steepener | Short ↓ / Long ↑ | −100 | −75 | −50 | 0 | +100 | +150 |
| Flattener | Short ↑ / Long ↓ | +100 | +75 | +50 | 0 | −100 | −150 |
| Short Up | Short-end shock ↑ | +250 | +200 | +150 | +75 | 0 | 0 |
| Short Down | Short-end shock ↓ | −250 | −200 | −150 | −75 | 0 | 0 |

Intermediate buckets are linearly interpolated between reference tenors.

### Supervisory Outlier Threshold

Per **BCBS 368 §99**: a bank is a supervisory outlier if `|ΔEVE| > 15% of Tier 1 Capital` under any prescribed scenario. This triggers mandatory supervisor notification and may result in a Pillar 2 capital add-on.

---

## Simplifications and Known Limitations

This is a portfolio model demonstrating the BCBS 368 framework. The following simplifications apply:

| Item | This model | Production model |
|---|---|---|
| NMD repricing | Fixed behavioural tenor | Deposit beta + run-off decay from customer data |
| Yield curve | Stylised USD curve (late 2024) | Live market data (Bloomberg / central bank) |
| Discount factor | Annual compounding at bucket midpoint | Exact day-count, continuous compounding |
| Currency | Single (USD) | Per-currency, then aggregated |
| Automatic options | Not modelled | Delta-equivalent cash flows per BCBS 368 §127 |
| Credit spread risk | Not modelled | CSRBB per BCBS 368 §10 |

---

## Installation

```bash
git clone https://github.com/yourusername/irrbb-model.git
cd irrbb-model
pip install -r requirements.txt
```

---

## Usage

### CLI

```bash
# Run with default Tier 1 = $500M
python main.py

# Override Tier 1 capital
python main.py --tier1 600
```

Output: console summary + 7 charts saved to `output/` + 3 CSV files.

### Streamlit Dashboard

```bash
streamlit run app.py
```

The dashboard allows:
- Editing balance sheet notionals, rates, and maturities
- Selecting any of the 6 BCBS 368 scenarios for detailed view
- Viewing the EVE waterfall (per-instrument attribution)
- Downloading results as CSV

### Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Sample Output

### BCBS 368 Scenario Results (default balance sheet, Tier 1 = $500M)

| Scenario | ΔNII ($M) | ΔEVE ($M) | \|ΔEVE\|/T1 | Status |
|---|---|---|---|---|
| Parallel Shift Up | −8.0 | −54.1 | 10.8% | WATCH |
| Parallel Shift Down | +8.0 | +69.4 | 13.9% | WATCH |
| Steepener | +3.9 | −12.7 | 2.5% | PASS |
| Flattener | −3.9 | +19.3 | 3.9% | PASS |
| Short Rates Up | −9.9 | −17.3 | 3.5% | PASS |
| Short Rates Down | +9.9 | +18.1 | 3.6% | PASS |

The balance sheet is **long duration on the asset side** — fixed-rate mortgages and long bonds — funded by short-term floating liabilities. This creates a classic asset-sensitive position: NII benefits when short rates rise, but EVE is exposed to parallel rate increases due to the duration mismatch.

---

## References

- Basel Committee on Banking Supervision. *Interest rate risk in the banking book.* BCBS 368, April 2016.
- BIS. *Basel Framework — Interest rate risk in the banking book (SRP31).* https://www.bis.org/basel_framework/

---

## License

MIT
