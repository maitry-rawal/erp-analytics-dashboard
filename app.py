"""Streamlit dashboard for manufacturing analytics."""

import sqlite3
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manufacturing.db")

# -- palette --
BLUE = "#2563eb"
BLUE_LIGHT = "#3b82f6"
GREEN = "#059669"
GREEN_LIGHT = "#10b981"
AMBER = "#d97706"
RED = "#ef4444"
RED_DARK = "#dc2626"

st.set_page_config(page_title="Manufacturing Analytics", layout="wide")


# ── data loading ────────────────────────────────────────────────────
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


pr, dt, qi = load_data()

# ── sidebar filters ─────────────────────────────────────────────────
st.sidebar.title("Filters")

all_lines = sorted(pr["line"].unique())
sel_lines = st.sidebar.multiselect("Production Line", all_lines, default=all_lines)

all_products = sorted(pr["product_type"].unique())
sel_products = st.sidebar.multiselect("Product Type", all_products, default=all_products)

# apply filters
mask_pr = pr["line"].isin(sel_lines) & pr["product_type"].isin(sel_products)
fpr = pr[mask_pr]

mask_qi = qi["line"].isin(sel_lines) & qi["product_type"].isin(sel_products)
fqi = qi[mask_qi]

# downtime links through machine; get machines present in filtered runs
machines_in_scope = fpr["machine"].unique()
fdt = dt[dt["machine"].isin(machines_in_scope)]


# ── helper ──────────────────────────────────────────────────────────
def kpi_card(label, value, suffix="", color=BLUE):
    st.markdown(
        f"""
        <div style="background:#fafafa;border-left:4px solid {color};
                    padding:12px 16px;border-radius:4px;margin-bottom:4px">
            <p style="margin:0;font-size:13px;color:#666">{label}</p>
            <p style="margin:0;font-size:28px;font-weight:700;color:#111">{value}{suffix}</p>
        </div>""",
        unsafe_allow_html=True,
    )


# ── tabs ────────────────────────────────────────────────────────────
tab_overview, tab_oee, tab_downtime, tab_quality = st.tabs(
    ["Overview", "OEE Analysis", "Downtime", "Quality"]
)

# ═══════════════════════════  OVERVIEW  ═════════════════════════════
with tab_overview:
    st.header("Overview")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Avg OEE", f"{fpr['oee'].mean():.1%}", color=BLUE)
    with c2:
        kpi_card("Total Downtime", f"{fdt['duration_hrs'].sum():,.1f}", suffix=" hrs", color=RED)
    with c3:
        kpi_card("First Pass Yield", f"{fqi['fpy'].mean():.1%}", color=GREEN)
    with c4:
        kpi_card("Total Units", f"{fpr['total_units'].sum():,}", color=AMBER)

    st.subheader("Daily OEE Trend")
    daily = fpr.groupby("date")["oee"].mean().reset_index()
    fig = px.line(daily, x="date", y="oee", labels={"oee": "OEE", "date": "Date"})
    fig.update_traces(line_color=BLUE)
    fig.update_layout(
        yaxis_tickformat=".0%",
        plot_bgcolor="white",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("OEE by Machine")
    by_machine = fpr.groupby("machine")["oee"].mean().sort_values().reset_index()
    fig2 = px.bar(
        by_machine,
        y="machine",
        x="oee",
        orientation="h",
        labels={"oee": "Avg OEE", "machine": ""},
    )
    fig2.update_traces(marker_color=BLUE_LIGHT)
    fig2.update_layout(
        xaxis_tickformat=".0%",
        plot_bgcolor="white",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)


# ═══════════════════════════  OEE ANALYSIS  ════════════════════════
with tab_oee:
    st.header("OEE Analysis")

    machines = ["All"] + sorted(fpr["machine"].unique())
    sel_machine = st.selectbox("Machine", machines)

    if sel_machine == "All":
        oee_df = fpr
    else:
        oee_df = fpr[fpr["machine"] == sel_machine]

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Availability", f"{oee_df['availability'].mean():.1%}", color=BLUE)
    with k2:
        kpi_card("Performance", f"{oee_df['performance'].mean():.1%}", color=GREEN)
    with k3:
        kpi_card("Quality", f"{oee_df['quality'].mean():.1%}", color=AMBER)

    # OEE components bar
    st.subheader("OEE Components")
    comp = pd.DataFrame({
        "Component": ["Availability", "Performance", "Quality"],
        "Value": [
            oee_df["availability"].mean(),
            oee_df["performance"].mean(),
            oee_df["quality"].mean(),
        ],
    })
    fig3 = go.Figure(
        go.Bar(
            x=comp["Component"],
            y=comp["Value"],
            marker_color=[BLUE, GREEN, AMBER],
            text=[f"{v:.1%}" for v in comp["Value"]],
            textposition="outside",
        )
    )
    fig3.update_layout(
        yaxis_tickformat=".0%",
        yaxis_range=[0, 1.05],
        plot_bgcolor="white",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    st.plotly_chart(fig3, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("OEE by Shift")
        by_shift = oee_df.groupby("shift")["oee"].mean().reset_index()
        fig4 = px.bar(
            by_shift,
            x="shift",
            y="oee",
            labels={"oee": "Avg OEE", "shift": "Shift"},
            color_discrete_sequence=[BLUE_LIGHT],
        )
        fig4.update_layout(
            yaxis_tickformat=".0%",
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig4, use_container_width=True)

    with col_b:
        st.subheader("OEE Distribution")
        fig5 = px.histogram(
            oee_df, x="oee", nbins=30,
            labels={"oee": "OEE"},
            color_discrete_sequence=[BLUE_LIGHT],
        )
        fig5.update_layout(
            xaxis_tickformat=".0%",
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig5, use_container_width=True)


# ═══════════════════════════  DOWNTIME  ════════════════════════════
with tab_downtime:
    st.header("Downtime Analysis")

    # pareto by category
    st.subheader("Downtime Pareto")
    pareto = (
        fdt.groupby("category")["duration_hrs"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    pareto["cumulative_pct"] = pareto["duration_hrs"].cumsum() / pareto["duration_hrs"].sum() * 100

    fig6 = go.Figure()
    fig6.add_bar(
        x=pareto["category"],
        y=pareto["duration_hrs"],
        name="Hours",
        marker_color=BLUE_LIGHT,
        yaxis="y",
    )
    fig6.add_scatter(
        x=pareto["category"],
        y=pareto["cumulative_pct"],
        name="Cumulative %",
        mode="lines+markers",
        marker_color=RED,
        yaxis="y2",
    )
    fig6.update_layout(
        yaxis=dict(title="Hours", side="left"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105]),
        plot_bgcolor="white",
        margin=dict(l=40, r=40, t=20, b=40),
        legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig6, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Downtime by Machine")
        by_m = fdt.groupby("machine")["duration_hrs"].sum().sort_values(ascending=False).reset_index()
        fig7 = px.bar(
            by_m, x="machine", y="duration_hrs",
            labels={"duration_hrs": "Hours", "machine": ""},
            color_discrete_sequence=[BLUE_LIGHT],
        )
        fig7.update_layout(
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig7, use_container_width=True)

    with col_d:
        st.subheader("Recent Downtime Events")
        recent = fdt.sort_values("date", ascending=False).head(20)[
            ["date", "machine", "category", "detail", "duration_min", "downtime_type"]
        ].copy()
        recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(recent, hide_index=True, use_container_width=True)


# ═══════════════════════════  QUALITY  ═════════════════════════════
with tab_quality:
    st.header("Quality")

    q1, q2 = st.columns(2)
    with q1:
        kpi_card("Avg First Pass Yield", f"{fqi['fpy'].mean():.1%}", color=GREEN)
    with q2:
        kpi_card("Avg Defect Rate", f"{fqi['defect_rate'].mean():.2%}", color=RED)

    st.subheader("First Pass Yield Trend")
    fpy_daily = fqi.groupby("date")["fpy"].mean().reset_index()
    fig8 = px.line(fpy_daily, x="date", y="fpy", labels={"fpy": "FPY", "date": "Date"})
    fig8.update_traces(line_color=GREEN)
    fig8.update_layout(
        yaxis_tickformat=".0%",
        plot_bgcolor="white",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    st.plotly_chart(fig8, use_container_width=True)

    col_e, col_f = st.columns(2)

    with col_e:
        st.subheader("Defect Rate by Product Type")
        by_prod = fqi.groupby("product_type")["defect_rate"].mean().reset_index()
        fig9 = px.bar(
            by_prod, x="product_type", y="defect_rate",
            labels={"defect_rate": "Defect Rate", "product_type": "Product Type"},
            color_discrete_sequence=[RED],
        )
        fig9.update_layout(
            yaxis_tickformat=".2%",
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig9, use_container_width=True)

    with col_f:
        st.subheader("FPY by Machine (worst first)")
        by_m_q = fqi.groupby("machine")["fpy"].mean().sort_values().reset_index()
        fig10 = px.bar(
            by_m_q, y="machine", x="fpy",
            orientation="h",
            labels={"fpy": "First Pass Yield", "machine": ""},
            color_discrete_sequence=[GREEN_LIGHT],
        )
        fig10.update_layout(
            xaxis_tickformat=".0%",
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig10, use_container_width=True)
