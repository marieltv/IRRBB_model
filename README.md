# IRRBB Regulatory Model — EVE & NII Sensitivity · Basel III / BCBS 368

[![CI](https://github.com/marieltv/IRRBB_model/actions/workflows/ci.yaml/badge.svg)](https://github.com/marieltv/IRRBB_model/actions)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 1. Problem
 
Banks are required under Basel III to measure and report their exposure to
interest rate risk in the banking book (IRRBB). The regulator — the Basel
Committee on Banking Supervision — prescribes an exact methodology in
**BCBS 368 (April 2016)**: six shock scenarios, 19 repricing time buckets,
and a supervisory outlier threshold tied to Tier 1 Capital.
 
Most implementations of this framework either use coarse time buckets
(collapsing 19 bands into 5 or 6), approximate EVE sensitivity via duration
rather than discounting, or treat each instrument as a single cash flow at
maturity. These shortcuts produce materially incorrect EVE figures — in
particular, they overstate sensitivity for amortising loans and miss the
convexity asymmetry between rate-up and rate-down scenarios.
 
---
 
## 2. Solution Overview & Technology Stack
 
A Python model that implements the BCBS 368 standardised framework without
shortcuts:
 
**Cash flow scheduling** — each instrument generates its full contractual
payment schedule. A 10-year amortising mortgage produces 120 monthly cash
flows; a 2-year fixed bond produces 5. Each cash flow is slotted into its
exact BCBS 368 bucket by tenor.
 
**Proper EVE discounting** — Economic Value of Equity sensitivity is computed
by discounting all cash flows at the base yield curve and again at the shocked
curve, then taking the difference. This correctly captures bond convexity:
the rate-down scenario produces a larger |ΔEVE| than the rate-up scenario for
equal shocks, consistent with standard fixed income theory.
 
**19 BCBS 368 time buckets** — exact repricing bands from Annex 2, Table 2.
Bucket assignment is derived automatically from instrument tenor — no manual
mapping that can silently produce wrong results.
 
**Shock interpolation** — the six prescribed scenarios define shocks at six
reference tenors (O/N, 1Y, 2Y, 5Y, 10Y, 20Y). Intermediate bucket shocks
are linearly interpolated, matching the BCBS standardised approach.
 
**Supervisory outlier detection** — |ΔEVE| > 15% of Tier 1 Capital triggers
an outlier flag per BCBS 368 §99, requiring supervisor notification and
potentially a Pillar 2 capital add-on.
 
---
## Methodology
 
### EVE
 
```
PV_base(i)    = Σ_k  CF_i[k] × 1 / (1 + r_base[k])^t_k
PV_shocked(i) = Σ_k  CF_i[k] × 1 / (1 + r_shocked[k])^t_k
 
ΔEVE = Σ_assets [PV_shocked - PV_base]
     - Σ_liabilities [PV_shocked - PV_base]
```
 
### NII (1-year horizon)
 
```
ΔNII = Σ_floating_assets    notional_i × shock_bp(bucket_i) / 10,000
     - Σ_floating_liabilities notional_i × shock_bp(bucket_i) / 10,000
```
 
### BCBS 368 Shock Scenarios
 
| Scenario | O/N | 1Y | 2Y | 5Y | 10Y | 20Y |
|---|---|---|---|---|---|---|
| Parallel Up | +200 | +200 | +200 | +200 | +200 | +200 |
| Parallel Down | −200 | −200 | −200 | −200 | −200 | −200 |
| Steepener | −100 | −75 | −50 | 0 | +100 | +150 |
| Flattener | +100 | +75 | +50 | 0 | −100 | −150 |
| Short Up | +250 | +200 | +150 | +75 | 0 | 0 |
| Short Down | −250 | −200 | −150 | −75 | 0 | 0 |
 
Shocks in basis points at reference tenors; linearly interpolated to all 19 buckets.
 
--- 
## Simplifications
 
| Item | This model | Production |
|---|---|---|
| NMD repricing | Fixed behavioural tenor | Deposit beta + run-off from customer data |
| Yield curve | Stylised USD (late 2024) | Live market data |
| Compounding | Annual at bucket midpoint | Exact day-count, continuous |
| Currency | Single (USD) | Per-currency, then aggregated |
| Automatic options | Not modelled | Delta-equivalent CFs per BCBS 368 §127 |
| CSRBB | Not modelled | Per BCBS 368 §10 |
 
--- 
## Stack
 
| Layer | Technology |
|---|---|
| Core model | Python 3.10–3.12, numpy, pandas |
| Visualisation | matplotlib (static), Plotly (dashboard) |
| Dashboard | Streamlit |
| Testing | pytest, pytest-cov |
| CI/CD | GitHub Actions (test · lint · smoke, 3 Python versions) |
 
---
 
## Project Structure
 
```
irrbb-model/
├── src/
│   ├── time_buckets.py    # 19 BCBS 368 repricing bands + years_to_bucket()
│   ├── cashflows.py       # Instrument: bullet_fixed, bullet_floating,
│   │                      #   amortising, demand_deposit — full CF schedule
│   ├── yield_curve.py     # Base curve + per-bucket shocked discounting
│   ├── balance_sheet.py   # Hypothetical bank (10 assets, 10 liabilities)
│   ├── scenarios.py       # 6 BCBS 368 shocks with interpolation
│   ├── calculator.py      # IRRBBCalculator: NII, EVE, gap, attribution
│   └── plots.py           # Matplotlib charts for static output
├── tests/
│   └── test_irrbb.py      # 43 unit tests
├── app.py                 # Streamlit dashboard
├── main.py                # CLI entry point
├── setup.cfg              # Coverage configuration
└── .github/workflows/
    └── ci.yml
```
 
---
  
## 3. Results
 
Default balance sheet: 10 assets, 10 liabilities, 514 scheduled cash flows.
Tier 1 Capital: $500M. Outlier threshold: $75M (15%).
 
| Scenario | ΔNII ($M) | ΔEVE ($M) | \|ΔEVE\|/T1 | Status |
|---|---|---|---|---|
| Parallel Shift Up | −8.0 | −54.1 | 10.8% | WATCH |
| Parallel Shift Down | +8.0 | +69.4 | 13.9% | WATCH |
| Steepener | +3.9 | −12.7 | 2.5% | PASS |
| Flattener | −3.9 | +19.3 | 3.9% | PASS |
| Short Rates Up | −9.9 | −17.3 | 3.5% | PASS |
| Short Rates Down | +9.9 | +18.1 | 3.6% | PASS |
 
The balance sheet is **long duration on the asset side** — fixed-rate mortgages
and long bonds funded by short-term floating liabilities. This produces the
classic asset-sensitive profile: NII benefits when short rates rise, but EVE
is exposed to parallel rate increases due to the duration mismatch.
 
The parallel down scenario produces a larger |ΔEVE| than parallel up (+69.4
vs −54.1) — this asymmetry is convexity, not a model error. It is correctly
captured because the model discounts cash flows nonlinearly rather than
applying a linear duration approximation.
 
---

 
## Installation
 
```bash
git clone https://github.com/marieltv/IRRBB_model.git
cd irrbb-model
pip install -r requirements.txt
```
 
```bash
# CLI
python main.py --tier1 500
 
# Dashboard
streamlit run app.py
 
# Tests
pytest tests/ -v --cov=src
```
 
---
 
## References
 
- Basel Committee on Banking Supervision. *Interest rate risk in the banking book.* BCBS 368, April 2016. https://www.bis.org/bcbs/publ/d368.pdf
- BIS. *Basel Framework — SRP31.* https://www.bis.org/basel_framework/
