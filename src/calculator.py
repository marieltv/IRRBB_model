"""
calculator.py
-------------
IRRBB calculation engine — proper cash flow discounting, 19 BCBS 368 buckets.

EVE methodology (BCBS 368 §119–121)
-------------------------------------
For each instrument, cash flows are pre-bucketed into an array of shape
(N_BUCKETS,). EVE sensitivity is computed by discounting those cash flows
at the base curve and again at the shocked curve, then taking the difference:

    PV_base(i)    = Σ_k  CF_i[k]  × DF_base[k]
    PV_shocked(i) = Σ_k  CF_i[k]  × DF_shocked[k]
    ΔPVE(i)       = PV_shocked(i) - PV_base(i)

    ΔEVE = Σ_assets ΔPVE(i)  -  Σ_liabilities ΔPVE(i)

This correctly accounts for:
  - Coupons and principal arriving at different times (full schedule)
  - Different shock magnitudes per bucket (non-parallel scenarios)
  - Discount rate flooring at 0% (no negative rates)

NII methodology (BCBS 368 §109–112)
--------------------------------------
NII is computed over a 1-year horizon. Only cash flows that reprice within
the horizon (floating-rate instruments) affect NII:

    ΔNII(i) = repricing_notional(i) × shock(bucket_i) / 10_000

    sign: +1 for assets, -1 for liabilities
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .cashflows import Instrument
from .scenarios import Scenario
from .yield_curve import YieldCurve, BASE_CURVE
from .time_buckets import BCBS_BUCKETS


@dataclass
class ScenarioResult:
    scenario:       Scenario
    delta_nii:      float
    delta_eve:      float
    delta_eve_pct:  float
    nii_asset:      float
    nii_liability:  float
    eve_asset:      float
    eve_liability:  float
    tier1:          float
    is_outlier:     bool
    is_watch:       bool

    @property
    def status(self) -> str:
        if self.is_outlier:
            return "OUTLIER"
        if self.is_watch:
            return "WATCH"
        return "PASS"


class IRRBBCalculator:
    """
    IRRBB calculator with proper cash flow discounting.

    Parameters
    ----------
    assets         : list of asset Instrument objects
    liabilities    : list of liability Instrument objects
    tier1_capital  : Tier 1 capital (USD millions)
    yield_curve    : YieldCurve instance (defaults to module-level BASE_CURVE)
    outlier_threshold : 0.15 (15%) per BCBS 368 §99
    watch_threshold   : 0.10 (10%) internal warning
    """

    def __init__(
        self,
        assets:            list[Instrument],
        liabilities:       list[Instrument],
        tier1_capital:     float = 500.0,
        yield_curve:       YieldCurve = None,
        outlier_threshold: float = 0.15,
        watch_threshold:   float = 0.10,
    ):
        self.assets = assets
        self.liabilities = liabilities
        self.tier1 = tier1_capital
        self.curve = yield_curve or BASE_CURVE
        self.outlier_thr = outlier_threshold
        self.watch_thr = watch_threshold

        # Pre-compute bucketed cash flows for each instrument (expensive, do once)
        self._asset_cfs = np.array([i.bucket_cashflows() for i in assets])      # (n_assets, 19)
        self._liab_cfs = np.array([i.bucket_cashflows() for i in liabilities])  # (n_liabs,  19)

    # ── EVE ───────────────────────────────────────────────────────────────────

    def _pv_matrix(
        self,
        cf_matrix: np.ndarray,        # shape (n_instruments, N_BUCKETS)
        shocks_bp: list[float] | None,
    ) -> np.ndarray:
        """
        Returns PV array of shape (n_instruments,).
        cf_matrix @ discount_factors  =  vector dot product per instrument.
        """
        rates = self.curve.shocked_rates(shocks_bp) if shocks_bp is not None \
            else self.curve.base_rates
        dfs = self.curve.discount_factors(rates)  # shape (N_BUCKETS,)
        return cf_matrix @ dfs                       # shape (n_instruments,)

    def calc_eve(self, scenario: Scenario) -> tuple[float, float, float]:
        """
        Returns (delta_eve, asset_contribution, liability_contribution).
        ΔEVE = [PV_shocked(assets) - PV_base(assets)]
               - [PV_shocked(liabs) - PV_base(liabs)]
        """
        pv_base_a = self._pv_matrix(self._asset_cfs, None)
        pv_shocked_a = self._pv_matrix(self._asset_cfs, scenario.shocks_bp)
        pv_base_l = self._pv_matrix(self._liab_cfs,  None)
        pv_shocked_l = self._pv_matrix(self._liab_cfs,  scenario.shocks_bp)

        eve_asset = float(np.sum(pv_shocked_a - pv_base_a))
        eve_liab = float(np.sum(pv_shocked_l - pv_base_l))
        return eve_asset - eve_liab, eve_asset, eve_liab

    # ── NII ───────────────────────────────────────────────────────────────────

    def _nii_side(
        self,
        instruments: list[Instrument],
        scenario:    Scenario,
        sign:        int,
    ) -> float:
        total = 0.0
        for inst in instruments:
            if inst.instrument_type in ("bullet_floating", "demand_deposit"):
                bucket = inst.cashflows[0].bucket   # single repricing CF
                shock_dec = scenario.shock_at_bucket(bucket) / 10_000
                total += sign * inst.notional * shock_dec
        return total

    def calc_nii(self, scenario: Scenario) -> tuple[float, float, float]:
        nii_a = self._nii_side(self.assets,      scenario, +1)
        nii_l = self._nii_side(self.liabilities, scenario, -1)
        return nii_a + nii_l, nii_a, nii_l

    # ── Full scenario ─────────────────────────────────────────────────────────

    def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        delta_nii, nii_a, nii_l = self.calc_nii(scenario)
        delta_eve, eve_a, eve_l = self.calc_eve(scenario)
        eve_pct = abs(delta_eve) / self.tier1 * 100

        return ScenarioResult(
            scenario=scenario,
            delta_nii=delta_nii,
            delta_eve=delta_eve,
            delta_eve_pct=eve_pct,
            nii_asset=nii_a,
            nii_liability=nii_l,
            eve_asset=eve_a,
            eve_liability=eve_l,
            tier1=self.tier1,
            is_outlier=eve_pct > self.outlier_thr * 100,
            is_watch=(eve_pct > self.watch_thr * 100)
            and (eve_pct <= self.outlier_thr * 100),
        )

    def run_all(self, scenarios: list[Scenario]) -> list[ScenarioResult]:
        return [self.run_scenario(s) for s in scenarios]

    # ── Repricing gap ─────────────────────────────────────────────────────────

    def repricing_gap(self) -> pd.DataFrame:
        """Notional repricing gap per BCBS 368 bucket (all 19)."""
        rows = []
        for b in BCBS_BUCKETS:
            a = sum(i.notional for i in self.assets
                    if any(cf.bucket == b.index for cf in i.cashflows))
            liab_total = sum(
                i.notional for i in self.liabilities
                if any(cf.bucket == b.index for cf in i.cashflows)
            )
            rows.append({"bucket": b.label, "assets": a,
                         "liabilities": liab_total, "net_gap": a - liab_total})
        return pd.DataFrame(rows).set_index("bucket")

    # ── Instrument-level EVE detail ───────────────────────────────────────────

    def instrument_eve_detail(self, scenario: Scenario) -> pd.DataFrame:
        """Per-instrument ΔEVE breakdown — useful for attribution."""
        rows = []
        sides = [
            (+1, self.assets, self._asset_cfs),
            (-1, self.liabilities, self._liab_cfs),
        ]
        for sign, instruments, cf_matrix in sides:
            pv_base = self._pv_matrix(cf_matrix, None)
            pv_shocked = self._pv_matrix(cf_matrix, scenario.shocks_bp)
            for inst, pv_b, pv_s in zip(instruments, pv_base, pv_shocked):
                delta_pv = sign * (pv_s - pv_b)
                rows.append({
                    "side":          inst.side.upper(),
                    "instrument":    inst.name,
                    "notional":      inst.notional,
                    "type":          inst.instrument_type,
                    "eff_duration":  round(inst.effective_duration, 2),
                    "pv_base":       round(sign * pv_b, 2),
                    "pv_shocked":    round(sign * pv_s, 2),
                    "delta_eve":     round(delta_pv, 2),
                })
        return pd.DataFrame(rows)

    # ── Summary table ─────────────────────────────────────────────────────────

    def summary_table(self, results: list[ScenarioResult]) -> pd.DataFrame:
        return pd.DataFrame([{
            "Scenario":      r.scenario.name,
            "Description":   r.scenario.description,
            "ΔNII ($M)":     round(r.delta_nii,     2),
            "ΔEVE ($M)":     round(r.delta_eve,     2),
            "|ΔEVE|/T1 (%)": round(r.delta_eve_pct, 1),
            "Status":        r.status,
        } for r in results])
