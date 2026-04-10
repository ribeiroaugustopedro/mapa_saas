import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
from modules.utils import haversine_vectorized

# --- CORE UTILS ---
def _compute_metrics(lat, lon, df_portfolio, radius_km):
    total_p = df_portfolio['user_id'].nunique() if 'user_id' in df_portfolio.columns else len(df_portfolio)
    res = {"portfolio": 0, "total_portfolio": total_p}
    if not df_portfolio.empty and "loc_latitude" in df_portfolio.columns:
        coords = df_portfolio.dropna(subset=['loc_latitude', 'loc_longitude'])
        if not coords.empty:
            dists = haversine_vectorized(lat, lon, coords['loc_latitude'].values, coords['loc_longitude'].values)
            mask = dists <= radius_km
            if 'user_id' in df_portfolio.columns:
                res["portfolio"] = coords.loc[mask, 'user_id'].nunique()
            else:
                res["portfolio"] = np.sum(mask)
    return res

def calculate_full_point_metrics(lat, lon, df_portfolio, radius_km):
    return _compute_metrics(lat, lon, df_portfolio, radius_km)

def identify_nearby_region(lat, lon, df_ref):
    if df_ref.empty: return {}
    cols_loc = ['loc_latitude', 'loc_longitude', 'latitude', 'longitude']
    available = [c for c in cols_loc if c in df_ref.columns]
    if len(available) < 2: return {}
    df_valid = df_ref.dropna(subset=available[:2])
    if df_valid.empty: return {}
    idx = np.argmin(haversine_vectorized(lat, lon, df_valid[available[0]].values, df_valid[available[1]].values))
    row = df_valid.iloc[idx]
    return {"Region": row.get("loc_region", "N/A"), "City": row.get("loc_city", "N/A")}

def render_kpi_card(title, value):
    st.markdown(f'''
        <div class="kpi-card">
            <div class="card-title">{title}</div>
            <div class="card-value">{value}</div>
        </div>
    ''', unsafe_allow_html=True)

# --- CHART ENGINE ---
def apply_chart_theme(chart, title=None):
    t = st.get_option("theme.textColor") or "#f8fafc"
    # Title is handled by markdown for better alignment and styling
    return chart.properties().configure_view(strokeWidth=0).configure_axis(
        grid=False, labelFontSize=11, titleFontSize=12, labelColor="#cbd5e1", 
        titleColor=t, domain=False, ticks=False, labelFontWeight="bold"
    )

PALETTE = ["#6366f1", "#8b5cf6", "#3b82f6", "#f59e0b", "#06b6d4", "#10b981", "#ec4899"]

def render_chart(df, col_name, color, label, id_col=None, chart_type="bar"):
    if df.empty or col_name not in df.columns: return
    df_clean = df.dropna(subset=[col_name])
    if df_clean.empty: return

    if id_col: data = df_clean.groupby(col_name)[id_col].nunique().reset_index(name="c")
    else: data = df_clean.groupby(col_name).size().reset_index(name="c")
    
    # Defensive cleaning and early return
    data["c"] = data["c"].fillna(0)
    if data.empty or data["c"].sum() == 0: return
    data = data.sort_values("c", ascending=False)
    
    st.markdown(f'''
        <div class="chart-title-box">
            <div class="card-title">{label}</div>
        </div>
    ''', unsafe_allow_html=True)
    
    # Calculate dynamic height for Altair
    h = max(200, len(data) * 26) if chart_type == "bar" else 300
    max_val = data["c"].max()
    
    # Explicit domain helps suppress "Infinite extent" warnings
    x_scale = alt.Scale(domain=[0, max_val * 1.15], zero=True)
    y_scale = alt.Scale(domain=[0, max_val * 1.15], zero=True)
    
    if chart_type == "bar":
        sort_op = alt.EncodingSortField(field="c", order="descending")
        base = alt.Chart(data).encode(
            y=alt.Y(f"{col_name}:N", sort=sort_op, title=None, axis=alt.Axis(labelLimit=100, minExtent=100)),
            x=alt.X("c:Q", axis=None, scale=x_scale)
        )
        bars = base.mark_bar(color=color, cornerRadiusEnd=3)
        text = base.mark_text(
            align='left', baseline='middle', dx=5, 
            color="#ffffff", fontWeight=700, fontSize=11
        ).encode(text=alt.Text("c:Q", format=",.0f"))
        chart_obj = (bars + text).resolve_scale(y='shared')
    else:
        sort_op = alt.EncodingSortField(field="c", order="descending")
        base = alt.Chart(data).encode(
            x=alt.X(f"{col_name}:N", sort=sort_op, title=None, axis=alt.Axis(labelLimit=100, minExtent=100)),
            y=alt.Y("c:Q", axis=None, scale=y_scale)
        )
        bars = base.mark_bar(color=color, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        text = base.mark_text(
            align='center', baseline='bottom', dy=-5, 
            color="#ffffff", fontWeight=700, fontSize=11
        ).encode(text=alt.Text("c:Q", format=",.0f"))
        chart_obj = (bars + text).resolve_scale(x='shared')

    chart_obj = apply_chart_theme(chart_obj.properties(height=h, width='container'), label)

    # Force identical wrapping and remove any potential padding mismatch
    with st.container(height=300 if chart_type == "bar" else 360, border=False):
        st.altair_chart(chart_obj, use_container_width=True)

# --- DASHBOARDS ---
def render_member_dashboard(df_portfolio):
    if df_portfolio.empty: return
    st.markdown("<h2 style='text-align: center; margin-top: 0; margin-bottom: 5px; padding-bottom: 0;'>Portfolio Dashboard</h2>", unsafe_allow_html=True)
    cid = 'user_id' if 'user_id' in df_portfolio.columns else 'member_id'
    total = df_portfolio[cid].nunique() if cid in df_portfolio.columns else len(df_portfolio)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Portfolio", f"{total:,}")
    with k2: render_kpi_card("Core Region", df_portfolio["loc_region"].value_counts().index[0] if "loc_region" in df_portfolio.columns and not df_portfolio["loc_region"].empty else "-")
    with k3: render_kpi_card("Main Product", df_portfolio["contract_product"].value_counts().index[0] if "contract_product" in df_portfolio.columns and not df_portfolio["contract_product"].empty else "-")
    with k4: render_kpi_card("Major Status", df_portfolio["contract_status"].value_counts().index[0] if "contract_status" in df_portfolio.columns and not df_portfolio["contract_status"].empty else "-")
    
    st.markdown('<hr class="dashboard-divider">', unsafe_allow_html=True)

    # Grid Breakdown (Geography -> Demographics)
    c1, c2, c3 = st.columns(3)
    with c1: render_chart(df_portfolio, "loc_region", PALETTE[0], "Region", cid)
    with c2: render_chart(df_portfolio, "loc_state", PALETTE[1], "State", cid)
    with c3: render_chart(df_portfolio, "loc_city", PALETTE[2], "City", cid)
    
    c4, c5, c6 = st.columns(3)
    with c4: render_chart(df_portfolio, "contract_type", PALETTE[3], "Type", cid)
    with c5: render_chart(df_portfolio, "contract_status", PALETTE[4], "Status", cid)
    with c6: render_chart(df_portfolio, "contract_product", PALETTE[5], "Product", cid)
    
    c7, c8, c9 = st.columns(3)
    with c7: render_chart(df_portfolio, "user_age_group", PALETTE[6], "Age Group", cid)

def render_provider_dashboard(df_providers):
    if df_providers.empty: return
    st.markdown("<h2 style='text-align: center; margin-top: 0; margin-bottom: 5px; padding-bottom: 0;'>Providers Dashboard</h2>", unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Providers", f"{len(df_providers):,}")
    with k2: render_kpi_card("Core Region", df_providers["loc_region"].value_counts().index[0] if "loc_region" in df_providers.columns and not df_providers["loc_region"].empty else "-")
    with k3: render_kpi_card("Main Type", df_providers["prov_type"].value_counts().index[0] if "prov_type" in df_providers.columns and not df_providers["prov_type"].empty else "-")
    with k4: render_kpi_card("Major Status", df_providers["contract_status"].value_counts().index[0] if "contract_status" in df_providers.columns and not df_providers["contract_status"].empty else "-")
    
    st.markdown('<hr class="dashboard-divider">', unsafe_allow_html=True)

    # Grid Breakdown
    c1, c2, c3 = st.columns(3)
    with c1: render_chart(df_providers, "loc_region", PALETTE[0], "Region")
    with c2: render_chart(df_providers, "loc_state", PALETTE[1], "State")
    with c3: render_chart(df_providers, "loc_city", PALETTE[2], "City")
    
    c4, c5, c6 = st.columns(3)
    with c4: render_chart(df_providers, "prov_type", PALETTE[3], "Type")
    with c5: render_chart(df_providers, "contract_status", PALETTE[4], "Status")
    
    # Bottom Detailed Detail
    if "prov_name" in df_providers.columns:
        st.markdown('<hr class="dashboard-divider">', unsafe_allow_html=True)
        render_chart(df_providers, "prov_name", "#6366f1", "Providers", chart_type="bar")
