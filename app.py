"""
app.py
------
IRRBB Model — Interactive Streamlit Dashboard
Basel III / BCBS 368 · 19 Buckets · Full Cash Flow Discounting

Run:  streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.cashflows     import Instrument
from src.yield_curve   import YieldCurve
from src.balance_sheet import get_instruments
from src.scenarios     import SCENARIOS
from src.calculator    import IRRBBCalculator
from src.time_buckets  import BUCKET_LABELS, BCBS_BUCKETS, N_BUCKETS

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IRRBB Model — BCBS 368",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colours ───────────────────────────────────────────────────────────────────
BG     = "#0a0c0f"; BG2    = "#0f1217"; BORDER = "#1e2530"
AMBER  = "#f0a500"; GREEN  = "#00c87a"; RED    = "#e03c3c"
BLUE   = "#4a9eff"; ORANGE = "#ff7a30"; PURPLE = "#9b7fff"
CYAN   = "#00c8c8"; YELLOW = "#ffe066"; DIM    = "#5a6478"; TEXT = "#c8d0dc"
SCENARIO_COLORS = [RED, BLUE, PURPLE, ORANGE, YELLOW, CYAN]

PLOTLY_BASE = dict(
    paper_bgcolor=BG, plot_bgcolor=BG2,
    font=dict(family="monospace", color=TEXT, size=11),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(gridcolor=BORDER, tickfont=dict(color=DIM)),
    yaxis=dict(gridcolor=BORDER, tickfont=dict(color=DIM)),
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Mono', monospace !important; }
.stApp { background-color: #0a0c0f; }
[data-testid="metric-container"] {
    background: #0f1217; border: 1px solid #1e2530;
    padding: 12px 16px; border-radius: 2px;
}
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace !important; font-size: 1.4rem !important; }
[data-testid="stSidebar"] { background-color: #0f1217; border-right: 1px solid #1e2530; }
[data-testid="stSidebar"] label { color: #5a6478 !important; font-size: 0.75rem !important; letter-spacing: 1px; }
.stTabs [data-baseweb="tab-list"] { background: #0f1217; border-bottom: 1px solid #1e2530; gap: 0; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #5a6478; border-radius: 0;
    padding: 8px 20px; font-size: 0.75rem; letter-spacing: 1px; }
.stTabs [aria-selected="true"] { background: #0a0c0f; color: #f0a500; border-bottom: 2px solid #f0a500; }
[data-testid="stDataFrame"] { border: 1px solid #1e2530; }
[data-testid="stNumberInput"] input { background: #0a0c0f; border: 1px solid #2a3040;
    color: #c8d0dc; font-family: monospace; }
hr { border-color: #1e2530; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — Analysis controls only
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f"<span style='color:{AMBER};font-size:11px;font-weight:600;letter-spacing:2px'>IRRBB MODEL</span><br>"
        f"<span style='color:{DIM};font-size:9px'>Basel III / BCBS 368 · April 2016</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Tier 1 capital ────────────────────────────────────────────────────────
    st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>REGULATORY PARAMETERS</span>", unsafe_allow_html=True)
    tier1 = st.number_input(
        "Tier 1 Capital (USD M)",
        value=500, min_value=50, max_value=10000, step=50,
    )
    st.caption(f"Outlier threshold: **${tier1 * 0.15:.0f}M** (15% of T1)")
    st.caption(f"Watch threshold:   **${tier1 * 0.10:.0f}M** (10% of T1)")
    st.divider()

    # ── Scenario selector ─────────────────────────────────────────────────────
    st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>ACTIVE SCENARIO</span>", unsafe_allow_html=True)
    selected_name = st.radio(
        "scenario",
        [s.name for s in SCENARIOS],
        label_visibility="collapsed",
    )
    selected_scenario = next(s for s in SCENARIOS if s.name == selected_name)

    # Shock summary for selected scenario
    st.divider()
    st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>SHOCK PROFILE</span>", unsafe_allow_html=True)
    ref_labels = ["O/N", "1Y", "2Y", "5Y", "10Y", "20Y"]
    for label, bp in zip(ref_labels, selected_scenario.ref_shocks_bp):
        color = GREEN if bp > 0 else (RED if bp < 0 else DIM)
        sign  = "+" if bp > 0 else ""
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;font-size:10px;margin:1px 0'>"
            f"<span style='color:{DIM}'>{label}</span>"
            f"<span style='color:{color};font-weight:600'>{sign}{bp} bp</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        f"<span style='color:{DIM};font-size:9px'>"
        f"Balance sheet: 10 assets · 10 liabilities<br>"
        f"Source: BCBS 368, Annex 2</span>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL RUN
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def run_model(tier1_cap: float):
    assets, liabilities = get_instruments()
    calc    = IRRBBCalculator(assets, liabilities, tier1_capital=tier1_cap)
    results = calc.run_all(SCENARIOS)
    gap     = calc.repricing_gap()
    return calc, results, gap, assets, liabilities

calc, results, gap, assets, liabilities = run_model(float(tier1))
active  = next(r for r in results if r.scenario.name == selected_name)
detail  = calc.instrument_eve_detail(selected_scenario)
curve   = YieldCurve()


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER + KPIs
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    f"<h2 style='color:{AMBER};font-size:18px;letter-spacing:2px;margin-bottom:2px'>"
    f"INTEREST RATE RISK IN THE BANKING BOOK</h2>"
    f"<p style='color:{DIM};font-size:10px;margin-top:0'>"
    f"BCBS 368 (April 2016) · 19 Repricing Buckets · "
    f"Full Cash Flow Discounting · 6 Prescribed Scenarios</p>",
    unsafe_allow_html=True,
)
st.divider()

total_a  = sum(i.notional for i in assets)
total_l  = sum(i.notional for i in liabilities)
total_cf = sum(len(i.cashflows) for i in assets + liabilities)
outliers = sum(1 for r in results if r.is_outlier)
watches  = sum(1 for r in results if r.is_watch)
worst    = max(results, key=lambda r: r.delta_eve_pct)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Assets",      f"${total_a:,.0f}M")
c2.metric("Total Liabilities", f"${total_l:,.0f}M")
c3.metric("Scheduled CFs",     f"{total_cf:,}")
c4.metric("Tier 1 Capital",    f"${tier1:,.0f}M")
c5.metric("Outlier Breaches",  str(outliers),
          delta="None ✓" if outliers == 0 else f"{outliers} breach(es)",
          delta_color="normal" if outliers == 0 else "inverse")
c6.metric("Worst |ΔEVE|/T1",   f"{worst.delta_eve_pct:.1f}%",
          delta=worst.scenario.name, delta_color="off")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "  ALL SCENARIOS  ",
    "  SCENARIO DETAIL  ",
    "  EVE WATERFALL  ",
    "  SCENARIO COMPARISON  ",
    "  REPRICING GAP  ",
    "  YIELD CURVE  ",
])


# ── TAB 1: All scenarios ──────────────────────────────────────────────────────
with tab1:
    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>BCBS 368 RESULTS TABLE</span>", unsafe_allow_html=True)
        rows = []
        for r in results:
            rows.append({
                "Scenario":       r.scenario.name,
                "Description":    r.scenario.description,
                "ΔNII ($M)":      f"{r.delta_nii:+.2f}",
                "ΔEVE ($M)":      f"{r.delta_eve:+.2f}",
                "|ΔEVE|/T1 (%)":  f"{r.delta_eve_pct:.1f}%",
                "Status":         r.status,
            })
        df_summary = pd.DataFrame(rows)

        def _style_status(val):
            if val == "OUTLIER": return f"color:{RED};font-weight:bold"
            if val == "WATCH":   return f"color:{AMBER}"
            return f"color:{GREEN}"

        def _style_signed(val):
            try:
                v = float(str(val).replace("%",""))
                return f"color:{GREEN}" if v >= 0 else f"color:{RED}"
            except: return ""

        st.dataframe(
            df_summary.style
                .applymap(_style_status, subset=["Status"])
                .applymap(_style_signed, subset=["ΔNII ($M)", "ΔEVE ($M)"]),
            use_container_width=True, hide_index=True, height=280,
        )

        csv_summary = df_summary.to_csv(index=False)
        st.download_button("⬇ Download CSV", csv_summary,
                           file_name="irrbb_summary.csv", mime="text/csv",
                           use_container_width=True)

    with col_r:
        st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>|ΔEVE| / TIER 1 — ALL SCENARIOS</span>", unsafe_allow_html=True)
        names  = [r.scenario.name for r in results]
        pcts   = [r.delta_eve_pct for r in results]
        colors = [RED if r.is_outlier else AMBER if r.is_watch else GREEN for r in results]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=pcts, marker_color=colors,
            text=[f"{v:.1f}%" for v in pcts], textposition="outside",
            textfont=dict(size=9), showlegend=False,
        ))
        fig.add_hline(y=15, line_color=RED,   line_dash="dash", line_width=1.5,
                      annotation_text="15% Outlier (BCBS 368 §99)",
                      annotation_font=dict(color=RED, size=9))
        fig.add_hline(y=10, line_color=AMBER, line_dash="dot",  line_width=1,
                      annotation_text="10% Watch",
                      annotation_font=dict(color=AMBER, size=9))
        fig.update_layout(**PLOTLY_BASE, height=310,
                          yaxis_title="|ΔEVE| / T1 (%)",
                          yaxis=dict(gridcolor=BORDER, ticksuffix="%"))
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 2: Active scenario detail ─────────────────────────────────────────────
with tab2:
    r = active
    status_color = RED if r.is_outlier else AMBER if r.is_watch else GREEN

    st.markdown(
        f"<h3 style='color:{AMBER};font-size:13px;letter-spacing:1px'>"
        f"{r.scenario.name.upper()} &nbsp;·&nbsp; "
        f"<span style='color:{status_color}'>{r.status}</span></h3>"
        f"<p style='color:{DIM};font-size:10px'>{r.scenario.description}</p>",
        unsafe_allow_html=True,
    )

    if r.is_outlier:
        st.error(
            f"⚠ SUPERVISORY OUTLIER — |ΔEVE| = ${abs(r.delta_eve):.1f}M exceeds "
            f"15% of Tier 1 (${tier1 * 0.15:.0f}M). "
            f"BCBS 368 §99: supervisor notification required."
        )
    elif r.is_watch:
        st.warning(
            f"~ WATCH — |ΔEVE| = {r.delta_eve_pct:.1f}% is approaching the 15% outlier threshold."
        )
    else:
        st.success(f"✓ PASS — |ΔEVE| = {r.delta_eve_pct:.1f}% is within the 15% outlier threshold.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Δ NII (1Y)",   f"${r.delta_nii:+.2f}M")
    m2.metric("Δ EVE",        f"${r.delta_eve:+.2f}M")
    m3.metric("|ΔEVE| / T1",  f"{r.delta_eve_pct:.1f}%")
    m4.metric("Asset EVE Δ",  f"${r.eve_asset:+.2f}M")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>SHOCK CURVE — {r.scenario.name.upper()}</span>", unsafe_allow_html=True)
        sc = selected_scenario
        color_idx = next(i for i, s in enumerate(SCENARIOS) if s.id == sc.id)
        hex_color = SCENARIO_COLORS[color_idx]
        r_int, g_int, b_int = [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=list(range(N_BUCKETS)), y=sc.shocks_bp,
            mode="lines+markers",
            line=dict(color=hex_color, width=2),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor=f"rgba({r_int},{g_int},{b_int},0.12)",
        ))
        fig2.add_hline(y=0, line_color=DIM, line_width=0.8)
        fig2.update_layout(
            **PLOTLY_BASE, height=260,
            xaxis=dict(
                tickvals=list(range(0, N_BUCKETS, 2)),
                ticktext=[BUCKET_LABELS[i] for i in range(0, N_BUCKETS, 2)],
                tickangle=-35, gridcolor=BORDER,
            ),
            yaxis=dict(title="Shock (bp)", gridcolor=BORDER),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_r:
        st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>NII DECOMPOSITION</span>", unsafe_allow_html=True)
        fig3 = go.Figure(data=[
            go.Bar(name="Asset repricing",    x=["Assets"],     y=[r.nii_asset],
                   marker_color=BLUE,   text=f"${r.nii_asset:+.1f}M",    textposition="outside"),
            go.Bar(name="Liability repricing", x=["Liabilities"], y=[r.nii_liability],
                   marker_color=ORANGE, text=f"${r.nii_liability:+.1f}M", textposition="outside"),
            go.Bar(name="Net ΔNII",            x=["Net"],         y=[r.delta_nii],
                   marker_color=GREEN if r.delta_nii >= 0 else RED,
                   text=f"${r.delta_nii:+.1f}M", textposition="outside"),
        ])
        fig3.add_hline(y=0, line_color=DIM, line_width=0.8)
        fig3.update_layout(
            **PLOTLY_BASE, height=260, barmode="group",
            yaxis=dict(title="Δ NII (USD M)", gridcolor=BORDER),
            legend=dict(font=dict(size=9), bgcolor=BG2, bordercolor=BORDER),
        )
        st.plotly_chart(fig3, use_container_width=True)


# ── TAB 3: EVE Waterfall ──────────────────────────────────────────────────────
with tab3:
    st.markdown(
        f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>"
        f"INSTRUMENT-LEVEL ΔEVE ATTRIBUTION — {selected_name.upper()}</span>",
        unsafe_allow_html=True,
    )

    df = detail.sort_values("delta_eve")
    labels = [f"{row['side'][:1]} · {row['instrument']}" for _, row in df.iterrows()]
    colors = [GREEN if v >= 0 else RED for v in df["delta_eve"]]

    fig4 = go.Figure(go.Bar(
        x=df["delta_eve"], y=labels,
        orientation="h",
        marker_color=colors, marker_line_color=BORDER, marker_line_width=0.5,
        text=[f"${v:+.1f}M" for v in df["delta_eve"]],
        textposition="outside", textfont=dict(size=9, color=TEXT),
    ))
    fig4.add_vline(x=0, line_color=DIM, line_width=0.8)
    fig4.update_layout(
        **PLOTLY_BASE,
        height=max(420, len(df) * 32 + 80),
        title=dict(
            text=f"Total ΔEVE: ${df['delta_eve'].sum():+.1f}M  ·  "
                 f"{selected_name}",
            font=dict(color=DIM, size=10),
        ),
        xaxis=dict(title="Δ EVE contribution (USD M)", gridcolor=BORDER),
        yaxis=dict(tickfont=dict(size=9), gridcolor=BORDER),
        showlegend=False,
    )
    st.plotly_chart(fig4, use_container_width=True)

    with st.expander("▼ Full attribution table"):
        st.dataframe(
            detail[["side","instrument","notional","type","eff_duration",
                    "pv_base","pv_shocked","delta_eve"]]
            .style.format({
                "notional":     "${:.0f}M",
                "eff_duration": "{:.2f}Y",
                "pv_base":      "${:.1f}M",
                "pv_shocked":   "${:.1f}M",
                "delta_eve":    "${:+.2f}M",
            }),
            use_container_width=True, hide_index=True,
        )

    st.download_button(
        "⬇ Download Attribution CSV", detail.to_csv(index=False),
        file_name=f"eve_attribution_{selected_scenario.id}.csv",
        mime="text/csv", use_container_width=True,
    )


# ── TAB 4: Scenario comparison (waterfall all 6) ──────────────────────────────
with tab4:
    st.markdown(
        f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>"
        f"ΔEVE ATTRIBUTION — ALL SCENARIOS SIDE BY SIDE</span>",
        unsafe_allow_html=True,
    )
    st.caption("Shows which instruments drive risk differently across rate environments.")

    # Build per-scenario total EVE per instrument
    inst_names = [i.name for i in assets] + [i.name for i in liabilities]
    sides      = ["A"] * len(assets) + ["L"] * len(liabilities)
    labels_short = [f"{s} · {n[:28]}" for s, n in zip(sides, inst_names)]

    fig5 = go.Figure()
    for s_obj, color in zip(SCENARIOS, SCENARIO_COLORS):
        d = calc.instrument_eve_detail(s_obj)
        fig5.add_trace(go.Bar(
            name=s_obj.name,
            x=d["delta_eve"].values,
            y=[f"{row['side'][:1]} · {row['instrument'][:28]}" for _, row in d.iterrows()],
            orientation="h",
            marker_color=color, opacity=0.85,
        ))

    fig5.add_vline(x=0, line_color=DIM, line_width=0.8)
    fig5.update_layout(
        **PLOTLY_BASE,
        height=max(480, len(inst_names) * 28 + 120),
        barmode="group",
        title=dict(text="Instrument ΔEVE across all 6 BCBS 368 scenarios",
                   font=dict(color=DIM, size=10)),
        xaxis=dict(title="Δ EVE contribution (USD M)", gridcolor=BORDER),
        yaxis=dict(tickfont=dict(size=8), gridcolor=BORDER),
        legend=dict(font=dict(size=9), bgcolor=BG2, bordercolor=BORDER,
                    orientation="h", yanchor="bottom", y=1.01),
    )
    st.plotly_chart(fig5, use_container_width=True)


# ── TAB 5: Repricing Gap ──────────────────────────────────────────────────────
with tab5:
    st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>REPRICING GAP — 19 BCBS 368 BUCKETS</span>", unsafe_allow_html=True)

    DISP = list(range(0, N_BUCKETS, 2))
    DISP_LABELS = [BUCKET_LABELS[i] for i in DISP]
    gap_r = gap.reset_index()
    x     = list(range(len(gap_r)))

    fig6 = make_subplots(rows=1, cols=2,
                         subplot_titles=["Asset vs Liability by Bucket",
                                         "Net Repricing Gap"])
    fig6.add_trace(go.Bar(x=x, y=gap_r["assets"],      name="Assets",
                          marker_color=BLUE,   opacity=0.85), row=1, col=1)
    fig6.add_trace(go.Bar(x=x, y=gap_r["liabilities"], name="Liabilities",
                          marker_color=ORANGE, opacity=0.85), row=1, col=1)
    fig6.add_trace(go.Bar(x=x, y=gap_r["net_gap"],
                          marker_color=[GREEN if v >= 0 else RED for v in gap_r["net_gap"]],
                          name="Net Gap", showlegend=False), row=1, col=2)
    fig6.add_hline(y=0, line_color=DIM, line_width=0.8, row=1, col=2)

    for col in (1, 2):
        fig6.update_xaxes(tickvals=DISP, ticktext=DISP_LABELS,
                          tickangle=-40, tickfont=dict(size=8), row=1, col=col)

    fig6.update_layout(**PLOTLY_BASE, height=400, barmode="group",
                       legend=dict(font=dict(size=9), bgcolor=BG2, bordercolor=BORDER))
    fig6.update_annotations(font_color=DIM, font_size=10)
    st.plotly_chart(fig6, use_container_width=True)

    net = gap["net_gap"]
    asset_s = gap[net > 0].index.tolist()
    liab_s  = gap[net < 0].index.tolist()
    if asset_s:
        st.success(f"Asset-sensitive (NII ↑ when rates ↑): {', '.join(asset_s[:5])}")
    if liab_s:
        st.warning(f"Liability-sensitive (NII ↑ when rates ↓): {', '.join(liab_s[:5])}")

    st.download_button("⬇ Download Gap CSV", gap.to_csv(),
                       file_name="repricing_gap.csv", mime="text/csv",
                       use_container_width=True)


# ── TAB 6: Yield Curve ────────────────────────────────────────────────────────
with tab6:
    st.markdown(f"<span style='color:{DIM};font-size:10px;letter-spacing:1px'>YIELD CURVE — BASE & SHOCKED</span>", unsafe_allow_html=True)

    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(
        x=list(range(N_BUCKETS)), y=curve.base_rates * 100,
        mode="lines+markers", name="Base curve",
        line=dict(color=AMBER, width=3), marker=dict(size=5),
    ))
    for s_obj, color in zip(SCENARIOS, SCENARIO_COLORS):
        shocked = curve.shocked_rates(s_obj.shocks_bp) * 100
        fig7.add_trace(go.Scatter(
            x=list(range(N_BUCKETS)), y=shocked,
            mode="lines", name=s_obj.name,
            line=dict(color=color, width=1.2, dash="dash"), opacity=0.75,
        ))
    fig7.update_layout(
        **PLOTLY_BASE, height=420,
        xaxis=dict(tickvals=list(range(0, N_BUCKETS, 2)),
                   ticktext=[BUCKET_LABELS[i] for i in range(0, N_BUCKETS, 2)],
                   tickangle=-35, gridcolor=BORDER),
        yaxis=dict(tickformat=".1f", ticksuffix="%",
                   title="Rate (%)", gridcolor=BORDER),
        legend=dict(font=dict(size=9), bgcolor=BG2, bordercolor=BORDER,
                    orientation="h", yanchor="bottom", y=1.01),
    )
    st.plotly_chart(fig7, use_container_width=True)
    st.caption(
        "Base curve is stylised (USD, late 2024) — not sourced from live market data. "
        "A production model would ingest the actual yield curve from Bloomberg "
        "or central bank publications."
    )


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f"<p style='color:{DIM};font-size:9px;text-align:center'>"
    f"BCBS 368 (April 2016) · Interest Rate Risk in the Banking Book · "
    f"Pillar 2 · Supervisory outlier: |ΔEVE| &gt; 15% Tier 1 Capital</p>",
    unsafe_allow_html=True,
)