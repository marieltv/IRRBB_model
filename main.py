"""
main.py — IRRBB Model v3
Basel III / BCBS 368 · 19 Buckets · Full Cash Flow Discounting
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from src import (get_instruments, SCENARIOS, IRRBBCalculator, BASE_CURVE,
                 plot_nii, plot_eve, plot_repricing_gap, plot_shock_curves,
                 plot_nii_decomposition, plot_instrument_eve_waterfall, plot_yield_curve)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def print_balance_sheet(assets, liabilities):
    for side, instruments in (("ASSETS", assets), ("LIABILITIES", liabilities)):
        print(f"\n  {side}")
        print(f"  {'Instrument':<40} {'Notional':>9} {'Rate':>6}  {'Type':<16}  {'Eff Dur':>7}  {'CFs':>5}")
        print("  " + "─" * 84)
        total = 0
        for i in instruments:
            print(f"  {i.name:<40} ${i.notional:>7.0f}M {i.coupon_pct:>5.2f}%  "
                  f"{i.instrument_type:<16}  {i.effective_duration:>6.2f}Y  {len(i.cashflows):>5}")
            total += i.notional
        print(f"  {'TOTAL':<40} ${total:>7.0f}M")


def print_summary(results, tier1):
    sep = "─" * 86
    print(f"\nBCBS 368 RESULTS  |  Tier 1: ${tier1:.0f}M  |  Outlier: ${tier1*0.15:.0f}M (15%)")
    print(sep)
    print(f"  {'Scenario':<24} {'ΔNII ($M)':>10} {'ΔEVE ($M)':>10} {'|ΔEVE|/T1':>10}  Status")
    print(sep)
    for r in results:
        flag = " ⚠ OUTLIER" if r.is_outlier else (" ~ WATCH" if r.is_watch else "")
        print(f"  {r.scenario.name:<24} {r.delta_nii:>+9.2f}M {r.delta_eve:>+9.2f}M "
              f"{r.delta_eve_pct:>9.1f}%  {r.status}{flag}")
    print(sep)
    outliers = [r for r in results if r.is_outlier]
    watches  = [r for r in results if r.is_watch]
    if outliers:
        print(f"\n  ⚠  {len(outliers)} outlier breach(es). BCBS 368 §99: supervisor notification required.")
    elif watches:
        print(f"\n  ~  {len(watches)} scenario(s) approaching outlier threshold. Internal review recommended.")
    else:
        print(f"\n  ✓  All scenarios within outlier threshold.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier1", type=float, default=500.0)
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\n" + "═"*86)
    print("  IRRBB MODEL v3 — Basel III / BCBS 368 (April 2016)")
    print("  19 Repricing Buckets · 6 Shock Scenarios · Full Cash Flow Discounting")
    print("═"*86)

    assets, liabilities = get_instruments()
    total_cfs = sum(len(i.cashflows) for i in assets + liabilities)
    print(f"\n  Balance sheet: {len(assets)} assets, {len(liabilities)} liabilities, {total_cfs} scheduled cash flows")
    print_balance_sheet(assets, liabilities)

    calc    = IRRBBCalculator(assets, liabilities, tier1_capital=args.tier1)
    results = calc.run_all(SCENARIOS)
    print_summary(results, args.tier1)

    # Save CSV outputs
    calc.summary_table(results).to_csv(os.path.join(OUTPUT_DIR, "irrbb_summary.csv"), index=False)
    ps_up  = next(r for r in results if r.scenario.id == "PS_UP")
    detail = calc.instrument_eve_detail(ps_up.scenario)
    detail.to_csv(os.path.join(OUTPUT_DIR, "eve_attribution_ps_up.csv"), index=False)
    calc.repricing_gap().to_csv(os.path.join(OUTPUT_DIR, "repricing_gap.csv"))

    print("\n  Generating charts...")
    gap = calc.repricing_gap()
    plot_shock_curves(SCENARIOS,              save_path=os.path.join(OUTPUT_DIR, "shock_curves.png"))
    plot_yield_curve(BASE_CURVE, SCENARIOS,   save_path=os.path.join(OUTPUT_DIR, "yield_curve.png"))
    plot_nii(results,                         save_path=os.path.join(OUTPUT_DIR, "nii_sensitivity.png"))
    plot_eve(results,                         save_path=os.path.join(OUTPUT_DIR, "eve_sensitivity.png"))
    plot_repricing_gap(gap,                   save_path=os.path.join(OUTPUT_DIR, "repricing_gap.png"))
    plot_nii_decomposition(results,           save_path=os.path.join(OUTPUT_DIR, "nii_decomposition.png"))
    plot_instrument_eve_waterfall(
        detail, ps_up.scenario.name,          save_path=os.path.join(OUTPUT_DIR, "eve_waterfall.png"))
    print("\n  Done.\n")


if __name__ == "__main__":
    main()