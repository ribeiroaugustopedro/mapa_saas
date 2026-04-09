import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
from modules.utils import haversine_vectorized

def _compute_metrics(lat, lon, df_portfolio, radius_km):
    """Core internal function to compute metrics for a single coordinate."""
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

@st.cache_data
def calculate_provider_coverage(df_providers, df_portfolio, radius_km):
    if df_providers.empty or 'loc_latitude' not in df_providers.columns:
        return None, pd.DataFrame()

    total_p = df_portfolio['user_id'].nunique() if not df_portfolio.empty and 'user_id' in df_portfolio.columns else len(df_portfolio)
    results = []

    for idx, row in df_providers.iterrows():
        if pd.isna(row['loc_latitude']) or pd.isna(row['loc_longitude']):
            continue
            
        m = _compute_metrics(row['loc_latitude'], row['loc_longitude'], df_portfolio, radius_km)
        results.append({
            "provider_name": row.get("prov_name", "Unknown"),
            "provider_id": row.get("prov_id", idx),
            "coverage": m["portfolio"], 
            "metrics": m,
            "provider_type": row.get("prov_type", "N/A")
        })
    
    df_res = pd.DataFrame(results)
    return (df_res.loc[df_res['coverage'].idxmax()] if not df_res.empty else None), df_res

@st.cache_data
def calculate_member_count_in_radius(df_providers, df_portfolio, radius_km):
    _, df_res = calculate_provider_coverage(df_providers, df_portfolio, radius_km)
    return df_res.set_index('provider_id')['metrics'].to_dict() if not df_res.empty else {}

def calculate_full_point_metrics(lat, lon, df_portfolio, radius_km):
    return _compute_metrics(lat, lon, df_portfolio, radius_km)

def identify_nearby_region(lat, lon, df_ref):
    if df_ref.empty:
        return {}
        
    cols_loc = ['loc_latitude', 'loc_longitude']
    if not all(c in df_ref.columns for c in cols_loc):
        # Fallback if columns are not prefixed
        cols_loc = ['latitude', 'longitude']
        if not all(c in df_ref.columns for c in cols_loc):
            return {}
        
    df_valid = df_ref.dropna(subset=cols_loc)
    if df_valid.empty:
        return {}
        
    lats = df_valid[cols_loc[0]].values
    lons = df_valid[cols_loc[1]].values
    dists = haversine_vectorized(lat, lon, lats, lons)
    idx_min = np.argmin(dists)
    
    row = df_valid.iloc[idx_min]
    
    info = {}
    
    # Check for direct English columns or loc_ prefixed ones
    col_mapping = {
        'Region': ['loc_region', 'region', 'Region'],
        'City': ['loc_city', 'city', 'City'],
        'Neighborhood': ['loc_neighborhood', 'neighborhood', 'Neighborhood'],
        'State': ['loc_state', 'state', 'State']
    }
    
    for display_key, candidate_cols in col_mapping.items():
        for col_name in candidate_cols:
            if col_name in row:
                val = row[col_name]
                if pd.notna(val) and str(val).strip() != "":
                    info[display_key] = val
                    break
    
    # Handle ZIP Code
    zip_cols = ['loc_zip_code', 'zip_code', 'ZIP Code', 'cep']
    for c in zip_cols:
        if c in row:
            val = row[c]
            if pd.notna(val) and str(val).strip() != "":
                info['ZIP Code'] = str(val)
                break

    return info

def render_kpi_card(title, value, subtext="", color=None):
    # Standard clean styling
    value_class = "card-value"
    val_style = f'style="color: {color} !important;"' if color else ""
    
    st.markdown(f"""
    <div class="dashboard-card" title="{value}">
        <div class="card-title">{title}</div>
        <div class="card-value-container">
            <div class="{value_class}" {val_style}>{value}</div>
        </div>
        <div class="card-subtext">{subtext}</div>
    </div>
    """, unsafe_allow_html=True)

def apply_chart_theme(chart, title=None):
    # Robust theme detection: check base AND background color
    theme_base = st.get_option("theme.base")
    bg_color = st.get_option("theme.backgroundColor")
    
    # Heuristic: if base is dark OR bg_color is a dark hex value
    is_dark = (theme_base == "dark") or (bg_color and bg_color.lower() in ["#0e1117", "#000000", "#111111"])
    
    text_color = "#FFFFFF" if is_dark else "#1e293b"
    label_color = "#cbd5e1" if is_dark else "#475569"
    grid_color = "#334155" if is_dark else "#f1f5f9"

    if title:
        chart = chart.properties(title=alt.TitleParams(
            text=title, 
            anchor='start', 
            fontSize=16, 
            fontWeight=700, 
            dy=-15,
            color=text_color
        ))

    return chart.properties(
        width='container'
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        gridColor=grid_color,
        gridDash=[3,3],
        labelFontSize=11,
        titleFontSize=12,
        titleFontWeight=600,
        labelColor=label_color,
        titleColor=text_color,
        domain=False,
        ticks=False,
        labelAngle=0
    ).configure_legend(
        labelColor=label_color,
        titleColor=text_color
    ).configure_title(
        color=text_color,
        fontSize=18,
        fontWeight=700,
        anchor='start',
        offset=20
    )

# Standard Theme Colors for Storytelling
COLOR_GEO_REGION = "#8b5cf6" # Purple
COLOR_GEO_STATE  = "#6366f1" # Indigo
COLOR_GEO_CITY   = "#3b82f6" # Blue
COLOR_SEGMENT    = "#f59e0b" # Amber
COLOR_STATUS     = "#10b981" # Emerald
COLOR_DEMO       = "#ec4899" # Pink
COLOR_MODAL      = "#06b6d4" # Cyan

def render_bar_chart(df, x_col, y_col, color, title, label_fmt=",.0f", horizontal=True):
    if df.empty:
        # Silently skip if no data to keep dashboard clean
        return

    x_axis = alt.X(f"{x_col}:Q", title=None, axis=alt.Axis(labels=False, grid=False))
    y_axis = alt.Y(f"{y_col}:N", sort="-x" if horizontal else None, title=None, axis=alt.Axis(labelLimit=200))
    
    if not horizontal:
        x_axis, y_axis = alt.X(f"{y_col}:N", title=None), alt.Y(f"{x_col}:Q", title=None, axis=alt.Axis(labels=False, grid=False))

    base = alt.Chart(df).encode(
        x=x_axis,
        y=y_axis,
        tooltip=[y_col, alt.Tooltip(x_col, format=label_fmt)]
    )

    bars = base.mark_bar(color=color, cornerRadiusEnd=4, opacity=0.9)
    
    bg_color = st.get_option("theme.backgroundColor")
    is_dark = (st.get_option("theme.base") == "dark") or (bg_color and bg_color.lower() in ["#0e1117", "#000000", "#111111"])
    text_color = "#FFFFFF" if is_dark else "#1e293b"
    
    labels = base.mark_text(
        align='left' if horizontal else 'center',
        baseline='middle' if horizontal else 'bottom',
        dx=5 if horizontal else 0,
        dy=0 if horizontal else -5,
        color=text_color,
        fontSize=11,
        fontWeight=600
    ).encode(
        text=alt.Text(f"{x_col}:Q", format=label_fmt)
    )

    chart = (bars + labels).properties(height=300)
    st.altair_chart(apply_chart_theme(chart, title), use_container_width=True)

def render_member_dashboard(df_members):
    if df_members.empty:
        return

    # Using Portfolio Accent Colors for charts
    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 600;'>Portfolio Analytics</h2>", unsafe_allow_html=True)
    
    # Standardized key for ID tracking
    col_id = 'user_id' if 'user_id' in df_members.columns else 'member_id' if 'member_id' in df_members.columns else None
    
    if col_id:
        total_members = df_members[col_id].nunique()
    else:
        total_members = len(df_members)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Members", f"{total_members:,}", "Beneficiaries")
    with k2: 
        top_p = "-"
        if "contract_product" in df_members.columns and not df_members["contract_product"].empty:
            top_p = df_members["contract_product"].value_counts().index[0]
        render_kpi_card("Top Product", top_p, "Volume")
    with k3:
        top_r = "-"
        if "loc_region" in df_members.columns and not df_members["loc_region"].empty:
            top_r = df_members["loc_region"].value_counts().index[0]
        render_kpi_card("Top Region", top_r, "Presence")
    with k4:
        top_f = "-"
        if "user_age_group" in df_members.columns and not df_members["user_age_group"].empty:
            top_f = df_members["user_age_group"].value_counts().index[0]
        render_kpi_card("Avg Age (Mode)", top_f, "Profile")

    st.markdown("---")
    
    # Storytelling Phase 1: Geographic Footprint (Macro to Micro)
    st.subheader("Geographic Distribution")
    col1, col2 = st.columns(2)
    with col1:
        if "loc_region" in df_members.columns:
            df_reg = df_members.groupby("loc_region")[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_reg.sort_values("count", ascending=False), "count", "loc_region", COLOR_GEO_REGION, "Region Breakdown")
    with col2:
        if "loc_state" in df_members.columns:
            df_st = df_members.groupby("loc_state")[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_st.sort_values("count", ascending=False).head(10), "count", "loc_state", COLOR_GEO_STATE, "Top 10 States")

    st.markdown("---")
    
    # Storytelling Phase 2: Product & Contract Strategic View
    st.subheader("Contract & Product Strategy")
    col3, col4 = st.columns(2)
    with col3:
        if "contract_product" in df_members.columns:
            df_prod = df_members.groupby("contract_product")[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_prod.sort_values("count", ascending=False).head(8), "count", "contract_product", COLOR_SEGMENT, "Product Portfolio")
    with col4:
        if "contract_status" in df_members.columns:
            df_stat = df_members.groupby("contract_status")[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_stat.sort_values("count", ascending=False), "count", "contract_status", COLOR_STATUS, "Contract Status")

    st.markdown("---")
    
    # Storytelling Phase 3: Demographic Insights
    st.subheader("Member Profiles")
    col5, col6 = st.columns(2)
    with col5:
        if "user_age_group" in df_members.columns:
            df_age = df_members.groupby("user_age_group")[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_age, "count", "user_age_group", COLOR_DEMO, "Age Distribution")
    with col6:
        col_type = "contract_type" if "contract_type" in df_members.columns else "contract_modality"
        if col_type in df_members.columns:
            df_type = df_members.groupby(col_type)[col_id or df_members.columns[0]].nunique().reset_index(name="count")
            render_bar_chart(df_type, "count", col_type, COLOR_MODAL, "Type/Modality")


def render_provider_dashboard(df_providers):
    if df_providers.empty:
        return

    # Using Providers Accent Colors
    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 600;'>Network Analytics</h2>", unsafe_allow_html=True)
    
    total_p = len(df_providers)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Network", f"{total_p}", "Providers")
    with k2: 
        top_t = "-"
        if "prov_type" in df_providers.columns and not df_providers["prov_type"].empty:
            top_t = df_providers["prov_type"].value_counts().index[0]
        render_kpi_card("Leading Segment", top_t, "Volume")
    with k3:
        top_r = "-"
        if "loc_region" in df_providers.columns and not df_providers["loc_region"].empty:
            top_r = df_providers["loc_region"].value_counts().index[0]
        render_kpi_card("Network Center", top_r, "Concentration")
    with k4:
        status = "-"
        if "prov_tax_id" in df_providers.columns and not df_providers["prov_tax_id"].empty:
             status = df_providers["prov_tax_id"].value_counts().index[0]
        render_kpi_card("Primary Status", status, "Predominant")

    st.markdown("---")
    
    # Storytelling Phase 1: Geographic Distribution
    st.subheader("Network Reach")
    c1, c2 = st.columns(2)
    with c1:
        if "loc_region" in df_providers.columns:
            df_reg = df_providers.groupby("loc_region").size().reset_index(name="count")
            render_bar_chart(df_reg.sort_values("count", ascending=False), "count", "loc_region", COLOR_GEO_REGION, "Provider Regions")
    with c2:
        if "loc_state" in df_providers.columns:
            df_st = df_providers.groupby("loc_state").size().reset_index(name="count")
            render_bar_chart(df_st.sort_values("count", ascending=False).head(10), "count", "loc_state", COLOR_GEO_STATE, "Top 10 States")

    st.markdown("---")
    
    # Storytelling Phase 2: Provider Capabilities
    st.subheader("Provider Segments")
    c3, c4 = st.columns(2)
    with c3:
        if "prov_type" in df_providers.columns:
            df_tipo = df_providers.groupby("prov_type").size().reset_index(name="count")
            render_bar_chart(df_tipo.sort_values("count", ascending=False), "count", "prov_type", COLOR_SEGMENT, "Specialty Distribution")
    with c4:
        if "loc_city" in df_providers.columns:
            df_mun = df_providers.groupby("loc_city").size().reset_index(name="count")
            render_bar_chart(df_mun.sort_values("count", ascending=False).head(10), "count", "loc_city", COLOR_GEO_CITY, "Leading Hubs (Cities)")
