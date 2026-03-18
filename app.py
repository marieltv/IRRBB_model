"""
app.py
------
IRRBB Model — Interactive Streamlit Dashboard
Basel III / BCBS 368 · 19 Buckets · Full Cash Flow Discounting

Run:  streamlit run app.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from src.balance_sheet import get_instruments  # noqa: E402
from src.calculator import IRRBBCalculator  # noqa: E402
from src.scenarios import SCENARIOS  # noqa: E402
from src.time_buckets import BUCKET_LABELS, N_BUCKETS  # noqa: E402
from src.yield_curve import YieldCurve  # noqa: E402

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IRRBB Model — BCBS 368",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette — light institutional theme ────────────────────────────────
BG        = "#f5f6fa"
BG2       = "#ffffff"
BG3       = "#eef0f7"
BORDER    = "#d0d5e8"
TEXT      = "#1a1f2e"
DIM       = "#6b7394"
NAVY      = "#1a3a6b"
BLUE      = "#1a56db"
RED       = "#c0392b"
GREEN     = "#1a7a4a"
AMBER     = "#b35c00"
ORANGE    = "#d4600a"
PURPLE    = "#6c3483"
CYAN      = "#0e7490"
TEAL      = "#0d6e6e"
YELLOW    = "#7d6608"

SCENARIO_COLORS = [RED, BLUE, PURPLE, ORANGE, TEAL, CYAN]

PLOTLY_BASE = dict(
    paper_bgcolor=BG2,
    plot_bgcolor=BG,
    font=dict(family="'IBM Plex Sans', Arial, sans-serif", color=TEXT, size=11),
    margin=dict(l=20, r=20, t=44, b=20),
)

AXIS_STYLE = dict(
    gridcolor=BORDER,
    linecolor=BORDER,
    tickfont=dict(color=DIM, size=10),
    title_font=dict(color=TEXT, size=11),
    zerolinecolor=BORDER,
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'IBM Plex Sans', sans-serif !important;
}}
.stApp {{
    background-color: {BG};
}}
[data-testid="stSidebar"] {{
    background-color: {BG2};
    border-right: 1px solid {BORDER};
}}
[data-testid="metric-container"] {{
    background: {BG2};
    border: 1px solid {BORDER};
    border-top: 3px solid {BLUE};
    padding: 14px 16px;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
[data-testid="stMetricValue"] {{
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.4rem !important;
    color: {NAVY} !important;
    font-weight: 600 !important;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.72rem !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    color: {DIM} !important;
    font-weight: 500 !important;
}}
[data-testid="stMetricDelta"] {{
    font-size: 0.75rem !important;
}}
.stTabs [data-baseweb="tab-list"] {{
    background: {BG2};
    border-bottom: 2px solid {BORDER};
    gap: 0;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    color: {DIM};
    border-radius: 0;
    padding: 10px 22px;
    font-size: 0.75rem;
    letter-spacing: 0.8px;
    font-weight: 500;
    text-transform: uppercase;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
}}
.stTabs [aria-selected="true"] {{
    background: {BG2};
    color: {BLUE};
    border-bottom: 2px solid {BLUE};
    font-weight: 600;
}}
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
[data-testid="stNumberInput"] input {{
    background: {BG};
    border: 1px solid {BORDER};
    color: {TEXT};
    font-family: 'IBM Plex Mono', monospace;
    border-radius: 4px;
}}
h1, h2, h3 {{
    font-family: 'IBM Plex Sans', sans-serif !important;
    color: {NAVY} !important;
    font-weight: 600 !important;
}}
hr {{
    border-color: {BORDER};
    margin: 12px 0;
}}
.section-label {{
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: {DIM};
    margin-bottom: 8px;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f"<div style='padding:4px 0 2px'>"
        f"<span style='font-size:13px;font-weight:700;color:{NAVY};"
        f"letter-spacing:1px'>IRRBB MODEL</span><br>"
        f"<span style='font-size:10px;color:{DIM}'>"
        f"Basel III / BCBS 368 · April 2016</span></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("<p class='section-label'>Regulatory Parameters</p>",
                unsafe_allow_html=True)
    tier1 = st.number_input(
        "Tier 1 Capital (USD M)",
        value=500, min_value=50, max_value=10000, step=50,
    )
    st.caption(
        f"Outlier threshold: **${tier1 * 0.15:.0f}M** (15% of T1)  \n"
        f"Watch threshold: **${tier1 * 0.10:.0f}M** (10% of T1)"
    )
    st.divider()

    st.markdown("<p class='section-label'>Active Scenario</p>",
                unsafe_allow_html=True)
    selected_name = st.radio(
        "scenario", [s.name for s in SCENARIOS],
        label_visibility="collapsed",
    )
    selected_scenario = next(s for s in SCENARIOS if s.name == selected_name)

    st.divider()
    st.markdown("<p class='section-label'>Shock Profile</p>",
                unsafe_allow_html=True)
    ref_labels = ["O/N", "1Y", "2Y", "5Y", "10Y", "20Y"]
    for label, bp in zip(ref_labels, selected_scenario.ref_shocks_bp):
        color = GREEN if bp > 0 else (RED if bp < 0 else DIM)
        sign = "+" if bp > 0 else ""
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:11px;padding:2px 0;font-family:monospace'>"
            f"<span style='color:{DIM}'>{label}</span>"
            f"<span style='color:{color};font-weight:600'>{sign}{bp} bp</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.divider()
    st.caption("Balance sheet: 10 assets · 10 liabilities  \nSource: BCBS 368, Annex 2")


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def run_model(tier1_cap: float):
    assets, liabilities = get_instruments()
    calc = IRRBBCalculator(assets, liabilities, tier1_capital=tier1_cap)
    results = calc.run_all(SCENARIOS)
    gap = calc.repricing_gap()
    return calc, results, gap, assets, liabilities


calc, results, gap, assets, liabilities = run_model(float(tier1))
active = next(r for r in results if r.scenario.name == selected_name)
detail = calc.instrument_eve_detail(selected_scenario)
curve = YieldCurve()


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    f"<h2 style='font-size:20px;letter-spacing:0.5px;margin-bottom:2px'>"
    f"Interest Rate Risk in the Banking Book</h2>"
    f"<p style='color:{DIM};font-size:11px;margin-top:0'>"
    f"BCBS 368 (April 2016) · 19 Repricing Buckets · "
    f"Full Cash Flow Discounting · 6 Prescribed Scenarios</p>",
    unsafe_allow_html=True,
)
st.divider()

total_a = sum(i.notional for i in assets)
total_l = sum(i.notional for i in liabilities)
total_cf = sum(len(i.cashflows) for i in assets + liabilities)
outliers = sum(1 for r in results if r.is_outlier)
watches = sum(1 for r in results if r.is_watch)
worst = max(results, key=lambda r: r.delta_eve_pct)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Assets",       f"${total_a:,.0f}M")
c2.metric("Total Liabilities",  f"${total_l:,.0f}M")
c3.metric("Scheduled CFs",      f"{total_cf:,}")
c4.metric("Tier 1 Capital",     f"${tier1:,.0f}M")
c5.metric(
    "Outlier Breaches", str(outliers),
    delta="None ✓" if outliers == 0 else f"{outliers} breach(es)",
    delta_color="normal" if outliers == 0 else "inverse",
)
c6.metric("Worst |ΔEVE|/T1", f"{worst.delta_eve_pct:.1f}%",
          delta=worst.scenario.name, delta_color="off")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "All Scenarios",
    "Scenario Detail",
    "EVE Waterfall",
    "Scenario Comparison",
    "Repricing Gap",
    "Yield Curve",
])


# ── TAB 1: All scenarios ──────────────────────────────────────────────────────
with tab1:
    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("<p class='section-label'>BCBS 368 Results</p>",
                    unsafe_allow_html=True)
        rows = []
        for r in results:
            rows.append({
                "Scenario":      r.scenario.name,
                "Description":   r.scenario.description,
                "ΔNII ($M)":     f"{r.delta_nii:+.2f}",
                "ΔEVE ($M)":     f"{r.delta_eve:+.2f}",
                "|ΔEVE|/T1 (%)": f"{r.delta_eve_pct:.1f}%",
                "Status":        r.status,
            })
        df_summary = pd.DataFrame(rows)

        def _style_status(val):
            if val == "OUTLIER":
                return f"color:{RED};font-weight:bold"
            if val == "WATCH":
                return f"color:{AMBER};font-weight:500"
            return f"color:{GREEN};font-weight:500"

        def _style_signed(val):
            try:
                v = float(str(val).replace("%", ""))
                return f"color:{GREEN}" if v >= 0 else f"color:{RED}"
            except Exception:
                return ""

        st.dataframe(
            df_summary.style
            .applymap(_style_status, subset=["Status"])
            .applymap(_style_signed, subset=["ΔNII ($M)", "ΔEVE ($M)"]),
            use_container_width=True, hide_index=True, height=280,
        )
        csv_summary = df_summary.to_csv(index=False)
        st.download_button(
            "⬇ Download CSV", csv_summary,
            file_name="irrbb_summary.csv", mime="text/csv",
            use_container_width=True,
        )

    with col_r:
        st.markdown("<p class='section-label'>|ΔEVE| / Tier 1 — All Scenarios</p>",
                    unsafe_allow_html=True)
        names = [r.scenario.name for r in results]
        pcts = [r.delta_eve_pct for r in results]
        bar_colors = [
            RED if r.is_outlier else AMBER if r.is_watch else BLUE
            for r in results
        ]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=pcts, marker_color=bar_colors,
            marker_line_color=BORDER, marker_line_width=1,
            text=[f"{v:.1f}%" for v in pcts], textposition="outside",
            textfont=dict(size=10, color=TEXT),
        ))
        fig.add_hline(y=15, line_color=RED, line_dash="dash", line_width=1.5,
                      annotation_text="15% Outlier (BCBS 368 §99)",
                      annotation_font=dict(color=RED, size=9))
        fig.add_hline(y=10, line_color=AMBER, line_dash="dot", line_width=1,
                      annotation_text="10% Watch",
                      annotation_font=dict(color=AMBER, size=9))
        fig.update_layout(
            **PLOTLY_BASE, height=310, showlegend=False,
            yaxis=dict(**AXIS_STYLE, ticksuffix="%",
                       title="|ΔEVE| / T1 (%)"),
            xaxis=dict(**AXIS_STYLE),
        )
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 2: Scenario detail ────────────────────────────────────────────────────
with tab2:
    r = active
    status_color = RED if r.is_outlier else AMBER if r.is_watch else GREEN
    sc_color_idx = next(i for i, s in enumerate(SCENARIOS) if s.id == r.scenario.id)
    sc_color = SCENARIO_COLORS[sc_color_idx]

    st.markdown(
        f"<h3 style='font-size:15px;color:{NAVY}'>"
        f"{r.scenario.name} &nbsp;"
        f"<span style='font-size:12px;color:{status_color};"
        f"background:{status_color}18;padding:3px 10px;"
        f"border-radius:3px;font-weight:600'>{r.status}</span></h3>"
        f"<p style='color:{DIM};font-size:11px'>{r.scenario.description}</p>",
        unsafe_allow_html=True,
    )

    if r.is_outlier:
        st.error(
            f"⚠ SUPERVISORY OUTLIER — |ΔEVE| = ${abs(r.delta_eve):.1f}M "
            f"exceeds 15% of Tier 1 (${tier1 * 0.15:.0f}M). "
            f"BCBS 368 §99: supervisor notification required."
        )
    elif r.is_watch:
        st.warning(
            f"|ΔEVE| = {r.delta_eve_pct:.1f}% — approaching the 15% outlier threshold."
        )
    else:
        st.success(
            f"✓ PASS — |ΔEVE| = {r.delta_eve_pct:.1f}% within the 15% threshold."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Δ NII (1Y)",  f"${r.delta_nii:+.2f}M")
    m2.metric("Δ EVE",       f"${r.delta_eve:+.2f}M")
    m3.metric("|ΔEVE| / T1", f"{r.delta_eve_pct:.1f}%")
    m4.metric("Asset EVE Δ", f"${r.eve_asset:+.2f}M")

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("<p class='section-label'>Rate Shock Profile</p>",
                    unsafe_allow_html=True)
        hex_c = sc_color.lstrip("#")
        r_int, g_int, b_int = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=list(range(N_BUCKETS)), y=selected_scenario.shocks_bp,
            mode="lines+markers",
            line=dict(color=sc_color, width=2.5),
            marker=dict(size=5, color=sc_color),
            fill="tozeroy",
            fillcolor=f"rgba({r_int},{g_int},{b_int},0.08)",
        ))
        fig2.add_hline(y=0, line_color=BORDER, line_width=1)
        fig2.update_layout(
            **PLOTLY_BASE, height=270, showlegend=False,
            xaxis=dict(
                **AXIS_STYLE,
                tickvals=list(range(0, N_BUCKETS, 2)),
                ticktext=[BUCKET_LABELS[i] for i in range(0, N_BUCKETS, 2)],
                tickangle=-35,
            ),
            yaxis=dict(**AXIS_STYLE, title="Shock (bp)"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_r:
        st.markdown("<p class='section-label'>NII Decomposition</p>",
                    unsafe_allow_html=True)
        fig3 = go.Figure(data=[
            go.Bar(
                name="Asset repricing",
                x=["Assets"], y=[r.nii_asset],
                marker_color=BLUE, marker_line_color=BORDER, marker_line_width=1,
                text=f"${r.nii_asset:+.1f}M", textposition="outside",
            ),
            go.Bar(
                name="Liability repricing",
                x=["Liabilities"], y=[r.nii_liability],
                marker_color=ORANGE, marker_line_color=BORDER, marker_line_width=1,
                text=f"${r.nii_liability:+.1f}M", textposition="outside",
            ),
            go.Bar(
                name="Net ΔNII",
                x=["Net"], y=[r.delta_nii],
                marker_color=GREEN if r.delta_nii >= 0 else RED,
                marker_line_color=BORDER, marker_line_width=1,
                text=f"${r.delta_nii:+.1f}M", textposition="outside",
            ),
        ])
        fig3.add_hline(y=0, line_color=BORDER, line_width=1)
        fig3.update_layout(
            **PLOTLY_BASE, height=270, barmode="group",
            yaxis=dict(**AXIS_STYLE, title="Δ NII (USD M)"),
            xaxis=dict(**AXIS_STYLE),
            legend=dict(font=dict(size=10), bgcolor=BG2,
                        bordercolor=BORDER, borderwidth=1),
        )
        st.plotly_chart(fig3, use_container_width=True)


# ── TAB 3: EVE Waterfall ──────────────────────────────────────────────────────
with tab3:
    st.markdown(
        f"<p class='section-label'>"
        f"Instrument-level ΔEVE Attribution — {selected_name}</p>",
        unsafe_allow_html=True,
    )

    df = detail.sort_values("delta_eve")
    bar_colors = [GREEN if v >= 0 else RED for v in df["delta_eve"]]
    labels = [
        f"{row['side'][:1]} · {row['instrument']}"
        for _, row in df.iterrows()
    ]

    fig4 = go.Figure(go.Bar(
        x=df["delta_eve"], y=labels,
        orientation="h",
        marker_color=bar_colors,
        marker_line_color=BORDER, marker_line_width=0.5,
        text=[f"${v:+.1f}M" for v in df["delta_eve"]],
        textposition="outside",
        textfont=dict(size=10, color=TEXT),
    ))
    fig4.add_vline(x=0, line_color=BORDER, line_width=1)
    fig4.update_layout(
        **PLOTLY_BASE,
        height=max(440, len(df) * 32 + 80),
        title=dict(
            text=f"Total ΔEVE: ${df['delta_eve'].sum():+.1f}M  ·  {selected_name}",
            font=dict(color=DIM, size=11),
        ),
        xaxis=dict(**AXIS_STYLE, title="Δ EVE contribution (USD M)"),
        yaxis=dict(**AXIS_STYLE, tickfont=dict(size=10, color=TEXT)),
        showlegend=False,
    )
    st.plotly_chart(fig4, use_container_width=True)

    with st.expander("▼ Full attribution table"):
        st.dataframe(
            detail[["side", "instrument", "notional", "type",
                    "eff_duration", "pv_base", "pv_shocked", "delta_eve"]]
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


# ── TAB 4: Scenario comparison ────────────────────────────────────────────────
with tab4:
    st.markdown(
        "<p class='section-label'>"
        "ΔEVE Attribution — All Scenarios Side by Side</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Shows which instruments drive risk differently across rate environments."
    )

    fig5 = go.Figure()
    for s_obj, color in zip(SCENARIOS, SCENARIO_COLORS):
        d = calc.instrument_eve_detail(s_obj)
        fig5.add_trace(go.Bar(
            name=s_obj.name,
            x=d["delta_eve"].values,
            y=[
                f"{row['side'][:1]} · {row['instrument'][:30]}"
                for _, row in d.iterrows()
            ],
            orientation="h",
            marker_color=color,
            marker_line_color=BORDER, marker_line_width=0.5,
            opacity=0.85,
        ))
    fig5.add_vline(x=0, line_color=BORDER, line_width=1)
    n_inst = len(assets) + len(liabilities)
    fig5.update_layout(
        **PLOTLY_BASE,
        height=max(500, n_inst * 28 + 120),
        barmode="group",
        title=dict(
            text="Instrument ΔEVE across all 6 BCBS 368 scenarios",
            font=dict(color=DIM, size=11),
        ),
        xaxis=dict(**AXIS_STYLE, title="Δ EVE contribution (USD M)"),
        yaxis=dict(**AXIS_STYLE, tickfont=dict(size=9, color=TEXT)),
        legend=dict(
            font=dict(size=10), bgcolor=BG2,
            bordercolor=BORDER, borderwidth=1,
            orientation="h", yanchor="bottom", y=1.01,
        ),
    )
    st.plotly_chart(fig5, use_container_width=True)


# ── TAB 5: Repricing Gap ──────────────────────────────────────────────────────
with tab5:
    st.markdown("<p class='section-label'>Repricing Gap — 19 BCBS 368 Buckets</p>",
                unsafe_allow_html=True)

    DISP = list(range(0, N_BUCKETS, 2))
    DISP_LABELS = [BUCKET_LABELS[i] for i in DISP]
    gap_r = gap.reset_index()
    x = list(range(len(gap_r)))

    fig6 = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Asset vs Liability by Bucket", "Net Repricing Gap"],
    )
    fig6.add_trace(
        go.Bar(x=x, y=gap_r["assets"], name="Assets",
               marker_color=BLUE, opacity=0.8,
               marker_line_color=BORDER, marker_line_width=0.5),
        row=1, col=1,
    )
    fig6.add_trace(
        go.Bar(x=x, y=gap_r["liabilities"], name="Liabilities",
               marker_color=ORANGE, opacity=0.8,
               marker_line_color=BORDER, marker_line_width=0.5),
        row=1, col=1,
    )
    fig6.add_trace(
        go.Bar(
            x=x, y=gap_r["net_gap"],
            marker_color=[GREEN if v >= 0 else RED for v in gap_r["net_gap"]],
            marker_line_color=BORDER, marker_line_width=0.5,
            name="Net Gap", showlegend=False,
        ),
        row=1, col=2,
    )
    fig6.add_hline(y=0, line_color=BORDER, line_width=1, row=1, col=2)

    for col in (1, 2):
        fig6.update_xaxes(
            tickvals=DISP, ticktext=DISP_LABELS,
            tickangle=-40, tickfont=dict(size=8, color=DIM),
            gridcolor=BORDER, linecolor=BORDER,
            row=1, col=col,
        )
        fig6.update_yaxes(
            gridcolor=BORDER, linecolor=BORDER,
            tickfont=dict(size=10, color=DIM),
            row=1, col=col,
        )

    fig6.update_layout(
        **PLOTLY_BASE, height=420, barmode="group",
        legend=dict(font=dict(size=10), bgcolor=BG2,
                    bordercolor=BORDER, borderwidth=1),
    )
    fig6.update_annotations(font_color=DIM, font_size=11)
    st.plotly_chart(fig6, use_container_width=True)

    net = gap["net_gap"]
    asset_s = gap[net > 0].index.tolist()
    liab_s = gap[net < 0].index.tolist()
    if asset_s:
        st.success(
            f"Asset-sensitive (NII ↑ when rates ↑): {', '.join(asset_s[:5])}"
        )
    if liab_s:
        st.warning(
            f"Liability-sensitive (NII ↑ when rates ↓): {', '.join(liab_s[:5])}"
        )

    st.download_button(
        "⬇ Download Gap CSV", gap.to_csv(),
        file_name="repricing_gap.csv", mime="text/csv",
        use_container_width=True,
    )


# ── TAB 6: Yield Curve ────────────────────────────────────────────────────────
with tab6:
    st.markdown("<p class='section-label'>Yield Curve — Base & Shocked</p>",
                unsafe_allow_html=True)

    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(
        x=list(range(N_BUCKETS)), y=curve.base_rates * 100,
        mode="lines+markers", name="Base curve",
        line=dict(color=NAVY, width=3),
        marker=dict(size=6, color=NAVY),
    ))
    for s_obj, color in zip(SCENARIOS, SCENARIO_COLORS):
        shocked = curve.shocked_rates(s_obj.shocks_bp) * 100
        fig7.add_trace(go.Scatter(
            x=list(range(N_BUCKETS)), y=shocked,
            mode="lines", name=s_obj.name,
            line=dict(color=color, width=1.5, dash="dash"),
            opacity=0.8,
        ))
    fig7.update_layout(
        **PLOTLY_BASE, height=440,
        xaxis=dict(
            **AXIS_STYLE,
            tickvals=list(range(0, N_BUCKETS, 2)),
            ticktext=[BUCKET_LABELS[i] for i in range(0, N_BUCKETS, 2)],
            tickangle=-35,
        ),
        yaxis=dict(
            **AXIS_STYLE,
            tickformat=".1f", ticksuffix="%",
            title="Rate (%)",
        ),
        legend=dict(
            font=dict(size=10), bgcolor=BG2,
            bordercolor=BORDER, borderwidth=1,
            orientation="h", yanchor="bottom", y=1.01,
        ),
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
    f"<p style='color:{DIM};font-size:10px;text-align:center'>"
    f"BCBS 368 (April 2016) · Interest Rate Risk in the Banking Book · "
    f"Pillar 2 · Supervisory outlier: |ΔEVE| > 15% Tier 1 Capital</p>",
    unsafe_allow_html=True,
)
