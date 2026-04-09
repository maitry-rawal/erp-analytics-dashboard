"""Manufacturing Analytics Dashboard — OEE, downtime, and quality tracking."""

import sqlite3
import os

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manufacturing.db")

st.set_page_config(page_title="Manufacturing Analytics", layout="wide", page_icon="📊")

# targets
OEE_TARGET = 0.85
FPY_TARGET = 0.95
DOWNTIME_TARGET_PCT = 5.0


@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    pr = pd.read_sql("SELECT * FROM production_runs", conn)
    dt = pd.read_sql("SELECT * FROM downtime_events", conn)
    qi = pd.read_sql("SELECT * FROM quality_inspections", conn)
    conn.close()
    pr["date"] = pd.to_datetime(pr["date"])
    dt["date"] = pd.to_datetime(dt["date"])
    qi["date"] = pd.to_datetime(qi["date"])
    return pr, dt, qi


def metric_card(label, value, delta=None, delta_color="normal", help_text=None):
    """Render a st.metric with optional help tooltip."""
    st.metric(label, value, delta=delta, delta_color=delta_color, help=help_text)


def oee_color(val):
    if val >= 0.85: return "#059669"
    if val >= 0.65: return "#d97706"
    return "#dc2626"


def add_target_line(fig, target, label, axis="y"):
    fig.add_hline(y=target, line_dash="dot", line_color="#94a3b8", line_width=1.5,
                  annotation_text=f"Target: {label}", annotation_position="top right",
                  annotation_font_color="#64748b", annotation_font_size=11)


# ── load + filter ──────────────────────────────────────────────────
pr, dt, qi = load_data()

st.sidebar.image("https://img.icons8.com/fluency/48/bar-chart.png", width=36)
st.sidebar.title("Filters")
st.sidebar.caption(f"Data: {pr['date'].min().strftime('%b %Y')} – {pr['date'].max().strftime('%b %Y')}")

sel_lines = st.sidebar.multiselect("Production Line", sorted(pr["line"].unique()), default=sorted(pr["line"].unique()))
sel_types = st.sidebar.multiselect("Product Type", sorted(pr["product_type"].unique()), default=sorted(pr["product_type"].unique()))
sel_shift = st.sidebar.multiselect("Shift", sorted(pr["shift"].unique()), default=sorted(pr["shift"].unique()))

fpr = pr[pr["line"].isin(sel_lines) & pr["product_type"].isin(sel_types) & pr["shift"].isin(sel_shift)]
fqi = qi[qi["line"].isin(sel_lines) & qi["product_type"].isin(sel_types)]
fdt = dt[dt["machine"].isin(fpr["machine"].unique())]

# period splits for delta calculation
mid = fpr["date"].min() + (fpr["date"].max() - fpr["date"].min()) / 2
first_half = fpr[fpr["date"] <= mid]
second_half = fpr[fpr["date"] > mid]

# ── header ─────────────────────────────────────────────────────────
st.title("📊 Manufacturing Analytics")
st.caption(f"{len(fpr):,} production runs · {len(fpr['machine'].unique())} machines · {len(fdt)} downtime events")

tab_overview, tab_oee, tab_downtime, tab_quality = st.tabs(
    ["📈 Overview", "⚙️ OEE Deep Dive", "🔧 Downtime", "✅ Quality"]
)

# ═══════════════════════════  OVERVIEW  ═════════════════════════════
with tab_overview:
    # KPIs with deltas
    c1, c2, c3, c4, c5 = st.columns(5)
    oee_now = second_half["oee"].mean() if len(second_half) else fpr["oee"].mean()
    oee_prev = first_half["oee"].mean() if len(first_half) else 0
    with c1:
        metric_card("OEE", f"{fpr['oee'].mean():.1%}",
                     delta=f"{(oee_now - oee_prev):.1%} vs prior period",
                     help_text=f"Target: {OEE_TARGET:.0%}")
    with c2:
        metric_card("Availability", f"{fpr['availability'].mean():.1%}")
    with c3:
        metric_card("Performance", f"{fpr['performance'].mean():.1%}")
    with c4:
        metric_card("Quality Rate", f"{fpr['quality'].mean():.1%}")
    with c5:
        failure_rate = fpr["failure"].mean() * 100
        metric_card("Failure Rate", f"{failure_rate:.1f}%",
                     delta=f"{'↑' if failure_rate > 3 else '↓'} {'High' if failure_rate > 3 else 'Normal'}",
                     delta_color="inverse")

    st.divider()

    # two-column layout: trend + heatmap
    left, right = st.columns([3, 2])

    with left:
        st.subheader("OEE Trend — Daily with 7-Day Moving Average")
        daily = fpr.groupby("date")["oee"].mean().reset_index()
        daily["ma7"] = daily["oee"].rolling(7, min_periods=1).mean()

        fig = go.Figure()
        fig.add_scatter(x=daily["date"], y=daily["oee"], mode="markers",
                        marker=dict(size=4, color="#93c5fd", opacity=0.5), name="Daily")
        fig.add_scatter(x=daily["date"], y=daily["ma7"], mode="lines",
                        line=dict(color="#2563eb", width=2.5), name="7-day MA")
        add_target_line(fig, OEE_TARGET, f"{OEE_TARGET:.0%}")
        fig.update_layout(yaxis_tickformat=".0%", plot_bgcolor="white", height=380,
                          margin=dict(l=40, r=20, t=30, b=40),
                          legend=dict(orientation="h", y=1.12))
        fig.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig, use_container_width=True)

        below_target = (daily["ma7"] < OEE_TARGET).sum()
        st.caption(f"⚠️ {below_target}/{len(daily)} days ({below_target/len(daily)*100:.0f}%) below {OEE_TARGET:.0%} target")

    with right:
        st.subheader("OEE Heatmap — Machine × Shift")
        pivot = fpr.pivot_table(values="oee", index="machine", columns="shift", aggfunc="mean")
        fig_heat = px.imshow(pivot, color_continuous_scale=["#dc2626", "#fbbf24", "#059669"],
                             zmin=0.4, zmax=0.85, aspect="auto",
                             labels=dict(color="OEE"), text_auto=".0%")
        fig_heat.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

        best = pivot.stack().idxmax()
        worst = pivot.stack().idxmin()
        st.caption(f"🏆 Best: **{best[0]}** ({best[1]}) at {pivot.loc[best]:.1%} · "
                   f"⚠️ Worst: **{worst[0]}** ({worst[1]}) at {pivot.loc[worst]:.1%}")

    st.divider()

    # bottom row: machine ranking + production volume
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Machine OEE Ranking")
        by_m = fpr.groupby("machine").agg(
            oee=("oee", "mean"), runs=("run_id", "count"), failures=("failure", "sum")
        ).sort_values("oee", ascending=True).reset_index()
        by_m["color"] = by_m["oee"].apply(oee_color)

        fig2 = go.Figure(go.Bar(
            y=by_m["machine"], x=by_m["oee"], orientation="h",
            marker_color=by_m["color"],
            text=[f"{v:.1%} ({f} failures)" for v, f in zip(by_m["oee"], by_m["failures"])],
            textposition="auto"
        ))
        fig2.add_vline(x=OEE_TARGET, line_dash="dot", line_color="#94a3b8")
        fig2.update_layout(xaxis_tickformat=".0%", plot_bgcolor="white", height=400,
                           margin=dict(l=10, r=20, t=10, b=40), xaxis_title="OEE")
        fig2.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig2, use_container_width=True)

    with right2:
        st.subheader("Weekly Production Volume")
        weekly = fpr.set_index("date").resample("W").agg(
            units=("total_units", "sum"), good=("good_units", "sum")
        ).reset_index()
        weekly["scrap"] = weekly["units"] - weekly["good"]

        fig3 = go.Figure()
        fig3.add_bar(x=weekly["date"], y=weekly["good"], name="Good Units", marker_color="#3b82f6")
        fig3.add_bar(x=weekly["date"], y=weekly["scrap"], name="Scrap", marker_color="#fca5a5")
        fig3.update_layout(barmode="stack", plot_bgcolor="white", height=400,
                           margin=dict(l=40, r=20, t=10, b=40),
                           legend=dict(orientation="h", y=1.08))
        fig3.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig3, use_container_width=True)


# ═══════════════════════════  OEE DEEP DIVE  ═══════════════════════
with tab_oee:
    sel_machine = st.selectbox("Select Machine", ["All Machines"] + sorted(fpr["machine"].unique()))
    oee_df = fpr if sel_machine == "All Machines" else fpr[fpr["machine"] == sel_machine]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        a = oee_df["availability"].mean()
        metric_card("Availability", f"{a:.1%}", help_text="Actual run time / planned time")
    with c2:
        p = oee_df["performance"].mean()
        metric_card("Performance", f"{p:.1%}", help_text="Actual throughput / ideal throughput")
    with c3:
        q = oee_df["quality"].mean()
        metric_card("Quality", f"{q:.1%}", help_text="Good units / total units")
    with c4:
        o = a * p * q
        metric_card("OEE", f"{o:.1%}", delta=f"{'Above' if o >= OEE_TARGET else 'Below'} {OEE_TARGET:.0%} target",
                     delta_color="normal" if o >= OEE_TARGET else "inverse")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("OEE Component Waterfall")
        # waterfall showing how A × P × Q = OEE
        fig_wf = go.Figure(go.Waterfall(
            x=["Availability", "Performance Loss", "Quality Loss", "OEE"],
            y=[a, -(a - a*p), -(a*p - a*p*q), 0],
            measure=["absolute", "relative", "relative", "total"],
            connector={"line": {"color": "#e2e8f0"}},
            decreasing={"marker": {"color": "#fca5a5"}},
            increasing={"marker": {"color": "#86efac"}},
            totals={"marker": {"color": "#2563eb"}},
            text=[f"{a:.1%}", f"-{(a - a*p):.1%}", f"-{(a*p - a*p*q):.1%}", f"{o:.1%}"],
            textposition="outside"
        ))
        fig_wf.update_layout(yaxis_tickformat=".0%", plot_bgcolor="white", height=350,
                             margin=dict(l=40, r=20, t=20, b=40), showlegend=False)
        fig_wf.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_wf, use_container_width=True)

    with right:
        st.subheader("OEE Distribution")
        fig_hist = go.Figure()
        fig_hist.add_histogram(x=oee_df["oee"], nbinsx=40, marker_color="#93c5fd", name="Runs")
        fig_hist.add_vline(x=OEE_TARGET, line_dash="dot", line_color="#dc2626",
                           annotation_text="Target", annotation_position="top right")
        fig_hist.add_vline(x=oee_df["oee"].mean(), line_dash="solid", line_color="#2563eb",
                           annotation_text=f"Mean: {oee_df['oee'].mean():.1%}",
                           annotation_position="top left")
        fig_hist.update_layout(xaxis_tickformat=".0%", plot_bgcolor="white", height=350,
                               margin=dict(l=40, r=20, t=20, b=40))
        fig_hist.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_hist, use_container_width=True)

    st.divider()

    # Tool wear impact analysis
    st.subheader("Tool Wear Impact on OEE")
    left3, right3 = st.columns(2)

    with left3:
        fig_scatter = px.scatter(oee_df, x="tool_wear_min", y="oee", color="failure",
                                 color_discrete_map={0: "#93c5fd", 1: "#ef4444"},
                                 labels={"tool_wear_min": "Tool Wear (min)", "oee": "OEE",
                                         "failure": "Machine Failure"},
                                 opacity=0.5)
        fig_scatter.update_layout(plot_bgcolor="white", height=350,
                                  margin=dict(l=40, r=20, t=20, b=40))
        fig_scatter.update_yaxes(tickformat=".0%", gridcolor="#f1f5f9")
        st.plotly_chart(fig_scatter, use_container_width=True)

        corr = oee_df[["tool_wear_min", "oee"]].corr().iloc[0, 1]
        st.caption(f"Correlation: **{corr:.3f}** — {'Weak' if abs(corr) < 0.3 else 'Moderate' if abs(corr) < 0.6 else 'Strong'} "
                   f"{'negative' if corr < 0 else 'positive'} relationship")

    with right3:
        # OEE by product type
        by_type = oee_df.groupby("product_type").agg(
            oee=("oee", "mean"), units=("total_units", "sum")
        ).reset_index()
        by_type["label"] = by_type.apply(
            lambda r: f"{r['product_type']}: {r['oee']:.1%} ({r['units']:,} units)", axis=1
        )
        fig_type = px.bar(by_type, x="product_type", y="oee",
                          color="product_type",
                          color_discrete_map={"H": "#059669", "M": "#d97706", "L": "#dc2626"},
                          text=[f"{v:.1%}" for v in by_type["oee"]])
        fig_type.update_layout(yaxis_tickformat=".0%", plot_bgcolor="white", height=350,
                               margin=dict(l=40, r=20, t=20, b=40), showlegend=False,
                               xaxis_title="Product Quality Tier", yaxis_title="Avg OEE")
        add_target_line(fig_type, OEE_TARGET, f"{OEE_TARGET:.0%}")
        fig_type.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_type, use_container_width=True)
        st.caption("H = High quality tier · M = Medium · L = Low — higher tiers have lower defect rates")


# ═══════════════════════════  DOWNTIME  ════════════════════════════
with tab_downtime:
    c1, c2, c3 = st.columns(3)
    with c1:
        total_dt = fdt["duration_hrs"].sum() if "duration_hrs" in fdt.columns else fdt["duration_min"].sum() / 60
        metric_card("Total Downtime", f"{total_dt:,.0f} hrs")
    with c2:
        metric_card("Events", f"{len(fdt)}")
    with c3:
        avg_dur = fdt["duration_min"].mean() if len(fdt) else 0
        metric_card("Avg Duration", f"{avg_dur:.0f} min")

    st.divider()

    left, right = st.columns([3, 2])

    with left:
        st.subheader("Downtime Pareto — 80/20 Analysis")
        pareto = fdt.groupby("category").agg(
            hours=("duration_min", lambda x: x.sum() / 60),
            events=("event_id", "count")
        ).sort_values("hours", ascending=False).reset_index()
        pareto["cum_pct"] = pareto["hours"].cumsum() / pareto["hours"].sum() * 100

        fig_p = make_subplots(specs=[[{"secondary_y": True}]])
        # color bars: red if in top 80%, grey if not
        colors = ["#ef4444" if c <= 80 else "#cbd5e1" for c in pareto["cum_pct"]]
        fig_p.add_bar(x=pareto["category"], y=pareto["hours"], name="Hours Lost",
                      marker_color=colors, text=[f"{h:.0f}h" for h in pareto["hours"]],
                      textposition="outside", secondary_y=False)
        fig_p.add_scatter(x=pareto["category"], y=pareto["cum_pct"], name="Cumulative %",
                          mode="lines+markers", marker=dict(color="#1e293b", size=7),
                          line=dict(color="#1e293b", width=2), secondary_y=True)
        fig_p.add_hline(y=80, line_dash="dot", line_color="#94a3b8", secondary_y=True,
                        annotation_text="80% threshold")
        fig_p.update_layout(plot_bgcolor="white", height=400,
                            margin=dict(l=40, r=40, t=30, b=40),
                            legend=dict(orientation="h", y=1.12))
        fig_p.update_yaxes(title_text="Hours", secondary_y=False, gridcolor="#f1f5f9")
        fig_p.update_yaxes(title_text="Cumulative %", secondary_y=True, range=[0, 105])
        st.plotly_chart(fig_p, use_container_width=True)

        top_cats = pareto[pareto["cum_pct"] <= 80]["category"].tolist()
        st.caption(f"🎯 Focus areas: **{', '.join(top_cats)}** account for 80% of all downtime")

    with right:
        st.subheader("Downtime by Machine")
        by_m = fdt.groupby("machine").agg(
            hours=("duration_min", lambda x: x.sum() / 60),
            events=("event_id", "count")
        ).sort_values("hours", ascending=False).reset_index()

        fig_m = go.Figure(go.Bar(
            x=by_m["machine"], y=by_m["hours"],
            marker_color=["#ef4444" if h > by_m["hours"].mean() else "#93c5fd" for h in by_m["hours"]],
            text=[f"{h:.0f}h ({e} events)" for h, e in zip(by_m["hours"], by_m["events"])],
            textposition="outside"
        ))
        fig_m.add_hline(y=by_m["hours"].mean(), line_dash="dot", line_color="#64748b",
                        annotation_text="Avg")
        fig_m.update_layout(plot_bgcolor="white", height=400,
                            margin=dict(l=40, r=20, t=30, b=40), xaxis_title="", yaxis_title="Hours")
        fig_m.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_m, use_container_width=True)

    st.divider()

    # Downtime detail breakdown
    st.subheader("Failure Detail Breakdown")
    detail = fdt.groupby(["category", "detail"]).agg(
        hours=("duration_min", lambda x: x.sum() / 60),
        events=("event_id", "count"),
        avg_min=("duration_min", "mean")
    ).reset_index().sort_values("hours", ascending=False)

    fig_tree = px.treemap(detail, path=["category", "detail"], values="hours",
                          color="hours", color_continuous_scale=["#fef2f2", "#dc2626"])
    fig_tree.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_tree, use_container_width=True)

    with st.expander("📋 Recent Downtime Events (last 25)"):
        recent = fdt.sort_values("date", ascending=False).head(25)[
            ["date", "machine", "category", "detail", "duration_min", "downtime_type"]
        ].copy()
        recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
        recent.columns = ["Date", "Machine", "Category", "Detail", "Duration (min)", "Type"]
        st.dataframe(recent, hide_index=True, use_container_width=True)


# ═══════════════════════════  QUALITY  ═════════════════════════════
with tab_quality:
    c1, c2, c3, c4 = st.columns(4)
    fpy_now = fqi[fqi["date"] > mid]["fpy"].mean() if len(fqi[fqi["date"] > mid]) else fqi["fpy"].mean()
    fpy_prev = fqi[fqi["date"] <= mid]["fpy"].mean() if len(fqi[fqi["date"] <= mid]) else 0
    with c1:
        metric_card("First Pass Yield", f"{fqi['fpy'].mean():.1%}",
                     delta=f"{(fpy_now - fpy_prev):.2%} vs prior",
                     help_text=f"Target: {FPY_TARGET:.0%}")
    with c2:
        metric_card("Defect Rate", f"{fqi['defect_rate'].mean():.2%}")
    with c3:
        metric_card("Total Defects", f"{fqi['defects'].sum():,}")
    with c4:
        metric_card("Total Inspected", f"{fqi['total_inspected'].sum():,}")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("First Pass Yield Trend")
        fpy_daily = fqi.groupby("date")["fpy"].mean().reset_index()
        fpy_daily["ma7"] = fpy_daily["fpy"].rolling(7, min_periods=1).mean()

        fig_fpy = go.Figure()
        fig_fpy.add_scatter(x=fpy_daily["date"], y=fpy_daily["fpy"], mode="markers",
                            marker=dict(size=3, color="#86efac", opacity=0.4), name="Daily")
        fig_fpy.add_scatter(x=fpy_daily["date"], y=fpy_daily["ma7"], mode="lines",
                            line=dict(color="#059669", width=2.5), name="7-day MA")
        add_target_line(fig_fpy, FPY_TARGET, f"{FPY_TARGET:.0%}")
        fig_fpy.update_layout(yaxis_tickformat=".0%", plot_bgcolor="white", height=380,
                              margin=dict(l=40, r=20, t=20, b=40),
                              legend=dict(orientation="h", y=1.12))
        fig_fpy.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_fpy, use_container_width=True)

    with right:
        st.subheader("Defect Rate by Product Tier")
        by_t = fqi.groupby("product_type").agg(
            defect_rate=("defect_rate", "mean"),
            defects=("defects", "sum"),
            inspected=("total_inspected", "sum")
        ).reset_index()

        fig_def = go.Figure(go.Bar(
            x=by_t["product_type"], y=by_t["defect_rate"],
            marker_color=["#059669", "#d97706", "#dc2626"],
            text=[f"{r:.2%}\n({d:,} defects)" for r, d in zip(by_t["defect_rate"], by_t["defects"])],
            textposition="outside"
        ))
        fig_def.update_layout(yaxis_tickformat=".1%", plot_bgcolor="white", height=380,
                              margin=dict(l=40, r=20, t=20, b=40),
                              xaxis_title="Product Quality Tier", yaxis_title="Defect Rate")
        fig_def.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig_def, use_container_width=True)
        st.caption("L (Low) tier products have ~6% higher defect rates than H (High) tier")

    st.divider()

    st.subheader("Machine Quality Performance")
    mq = fqi.groupby("machine").agg(
        fpy=("fpy", "mean"), defects=("defects", "sum"), inspected=("total_inspected", "sum")
    ).reset_index().sort_values("fpy")
    mq["defect_rate"] = mq["defects"] / mq["inspected"]

    fig_mq = go.Figure()
    fig_mq.add_bar(x=mq["machine"], y=mq["fpy"], name="FPY",
                   marker_color=[oee_color(v) for v in mq["fpy"]],
                   text=[f"{v:.1%}" for v in mq["fpy"]], textposition="outside")
    add_target_line(fig_mq, FPY_TARGET, f"{FPY_TARGET:.0%}")
    fig_mq.update_layout(yaxis_tickformat=".0%", plot_bgcolor="white", height=380,
                         margin=dict(l=40, r=20, t=20, b=40), yaxis_title="First Pass Yield")
    fig_mq.update_yaxes(gridcolor="#f1f5f9", range=[0.8, 1.0])
    st.plotly_chart(fig_mq, use_container_width=True)

    worst_m = mq.iloc[0]
    st.caption(f"⚠️ **{worst_m['machine']}** has the lowest FPY at {worst_m['fpy']:.1%} "
               f"with {worst_m['defects']:,} total defects — investigate root cause")
