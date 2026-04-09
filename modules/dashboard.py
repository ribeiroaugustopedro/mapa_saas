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
    </div>
    """, unsafe_allow_html=True)

def get_theme_colors():
    # Use Streamlit's own theme colors as source of truth
    text_color = st.get_option("theme.textColor")
    bg_color = st.get_option("theme.backgroundColor")
    
    # If we can get st.get_option, use it. Otherwise fallback.
    # We want to know if we are in dark mode to decide on bar labels
    is_dark_base = True
    if text_color:
        # If text is dark (e.g. #31333F), it's Light Mode
        t = text_color.lower().lstrip('#')
        if len(t) == 3: t = ''.join([c*2 for c in t])
        if len(t) == 6:
            r, g, b = int(t[0:2],16), int(t[2:4],16), int(t[4:6],16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            if brightness > 128: is_dark_base = True # Light text -> Dark Mode
            else: is_dark_base = False # Dark text -> Light Mode
    
    if is_dark_base:
        return {
            "title": text_color if text_color else "#f8fafc",
            "axis": "#cbd5e1",
            "grid": "#334155",
            "bar_label": "#ffffff",
            "is_dark": True
        }
    else:
        return {
            "title": text_color if text_color else "#1e293b",
            "axis": "#475569",
            "grid": "#f1f5f9",
            "bar_label": "#ffffff",
            "is_dark": False
        }

def apply_chart_theme(chart, title=None):
    colors = get_theme_colors()
    
    if title:
        chart = chart.properties(title=alt.TitleParams(
            text=title, 
            anchor='start', 
            fontSize=16, 
            fontWeight=700, 
            dy=-15,
            color=colors["title"]
        ))

    return chart.properties(
        width='container'
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        gridColor=colors["grid"],
        gridDash=[3,3],
        labelFontSize=11,
        titleFontSize=12,
        titleFontWeight=600,
        labelColor=colors["axis"],
        titleColor=colors["title"],
        domain=False,
        ticks=False,
        labelAngle=0
    ).configure_legend(
        labelColor=colors["axis"],
        titleColor=colors["title"]
    ).configure_title(
        color=colors["title"],
        fontSize=18,
        fontWeight=700,
        anchor='start',
        offset=20
    )

# Dimension Color Palette (Unified cross-dashboard)
DIM_REGION  = "#6366f1" # Indigo
DIM_STATE   = "#8b5cf6" # Violet
DIM_CITY    = "#3b82f6" # Blue
DIM_PRODUCT = "#f59e0b" # Amber
DIM_TYPE    = "#06b6d4" # Cyan
DIM_STATUS  = "#10b981" # Emerald
DIM_AGE     = "#ec4899" # Pink
DIM_NAME    = "#f43f5e" # Rose

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
    
    colors = get_theme_colors()
    
    labels = base.mark_text(
        align='left' if horizontal else 'center',
        baseline='middle' if horizontal else 'bottom',
        dx=8 if horizontal else 0,
        dy=0 if horizontal else -8,
        color=colors["bar_label"],
        fontSize=11,
        fontWeight=600,
        clip=False
    ).encode(
        text=alt.Text(f"{x_col}:Q", format=label_fmt)
    )

    chart = (bars + labels).properties(height=300)
    # Add padding to avoid cut labels
    chart = chart.configure_view(strokeWidth=0).configure_axis(grid=False).properties(padding={"right": 50, "top": 10})
    st.altair_chart(apply_chart_theme(chart, title), use_container_width=True)

def render_member_dashboard(df_members):
    if df_members.empty: return

    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 700; color: {get_theme_colors()['title']};'>Members Dashboard</h2>", unsafe_allow_html=True)
    
    col_id = 'user_id' if 'user_id' in df_members.columns else 'member_id'
    total_members = df_members[col_id].nunique() if col_id in df_members.columns else len(df_members)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Active Members", f"{total_members:,}", "Beneficiaries")
    with k2: 
        top_p = df_members["contract_product"].value_counts().index[0] if "contract_product" in df_members.columns and not df_members["contract_product"].empty else "-"
        render_kpi_card("Dominant Product", top_p, "Portfolio Lead")
    with k3:
        top_r = df_members["loc_region"].value_counts().index[0] if "loc_region" in df_members.columns and not df_members["loc_region"].empty else "-"
        render_kpi_card("Market Center", top_r, "Region Lead")
    with k4:
        top_f = df_members["user_age_group"].value_counts().index[0] if "user_age_group" in df_members.columns and not df_members["user_age_group"].empty else "-"
        render_kpi_card("Prime Demographic", top_f, "Age Range")

    st.markdown("---")
    
    # Story 1: Market Footprint
    st.subheader("Market Coverage")
    g1, g2, g3 = st.columns(3)
    with g1:
        if "loc_region" in df_members.columns:
            df_reg = df_members.groupby("loc_region")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_reg.sort_values("count", ascending=False), "count", "loc_region", DIM_REGION, "Regional Split")
    with g2:
        if "loc_state" in df_members.columns:
            df_st = df_members.groupby("loc_state")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_st.sort_values("count", ascending=False).head(10), "count", "loc_state", DIM_STATE, "State Ranking")
    with g3:
        if "loc_city" in df_members.columns:
            df_city = df_members.groupby("loc_city")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_city.sort_values("count", ascending=False).head(10), "count", "loc_city", DIM_CITY, "City Hubs")

    st.markdown("---")
    
    # Story 2: Product & Profiles
    st.subheader("Structure & Demographics")
    m1, m2, m3 = st.columns(3)
    with m1:
        if "contract_product" in df_members.columns:
            df_p = df_members.groupby("contract_product")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_p.sort_values("count", ascending=False), "count", "contract_product", DIM_PRODUCT, "Product Mix")
    with m2:
        if "user_age_group" in df_members.columns:
            df_a = df_members.groupby("user_age_group")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_a, "count", "user_age_group", DIM_AGE, "Age Distribution")
    with m3:
        col_type = "contract_type" if "contract_type" in df_members.columns else "contract_modality"
        if col_type in df_members.columns:
            df_t = df_members.groupby(col_type)[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_t, "count", col_type, DIM_TYPE, "Contract Types")

    st.markdown("---")
    
    # Story 3: Health Status
    st.subheader("Operational Status")
    r1, _ = st.columns([1, 1])
    with r1:
        if "contract_status" in df_members.columns:
            df_s = df_members.groupby("contract_status")[col_id].nunique().reset_index(name="count")
            render_bar_chart(df_s, "count", "contract_status", DIM_STATUS, "Operational Status")

def render_provider_dashboard(df_providers):
    if df_providers.empty: return

    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 700; color: {get_theme_colors()['title']};'>Providers Dashboard</h2>", unsafe_allow_html=True)
    
    total_p = len(df_providers)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Network Points", f"{total_p:,}", "Service Units")
    with k2: 
        top_t = df_providers["prov_type"].value_counts().index[0] if "prov_type" in df_providers.columns and not df_providers["prov_type"].empty else "-"
        render_kpi_card("Core Specialization", top_t, "Network Lead")
    with k3:
        top_r = df_providers["loc_region"].value_counts().index[0] if "loc_region" in df_providers.columns and not df_providers["loc_region"].empty else "-"
        render_kpi_card("Strategic Center", top_r, "Presence Lead")
    with k4:
        status = df_providers["contract_status"].value_counts().index[0] if "contract_status" in df_providers.columns and not df_providers["contract_status"].empty else "-"
        render_kpi_card("Agreement Status", status, "Operational Lead")

    st.markdown("---")
    
    # Analysis Row 1: Geography
    st.subheader("Market Availability")
    p1, p2, p3 = st.columns(3)
    with p1:
        if "loc_region" in df_providers.columns:
            df_reg = df_providers.groupby("loc_region").size().reset_index(name="count")
            render_bar_chart(df_reg.sort_values("count", ascending=False), "count", "loc_region", DIM_REGION, "Regional Split")
    with p2:
        if "loc_state" in df_providers.columns:
            df_st = df_providers.groupby("loc_state").size().reset_index(name="count")
            render_bar_chart(df_st.sort_values("count", ascending=False).head(10), "count", "loc_state", DIM_STATE, "State Ranking")
    with p3:
        if "loc_city" in df_providers.columns:
            df_mun = df_providers.groupby("loc_city").size().reset_index(name="count")
            render_bar_chart(df_mun.sort_values("count", ascending=False).head(10), "count", "loc_city", DIM_CITY, "City Hubs")

    st.markdown("---")
    
    # Analysis Row 2: Operational Intelligence
    st.subheader("Network Intel")
    s1, s2, s3 = st.columns(3)
    with s1:
        if "contract_status" in df_providers.columns:
            df_status = df_providers.groupby("contract_status").size().reset_index(name="count")
            render_bar_chart(df_status.sort_values("count", ascending=False), "count", "contract_status", DIM_STATUS, "Operational Status")
    with s2:
        if "prov_type" in df_providers.columns:
            df_tipo = df_providers.groupby("prov_type").size().reset_index(name="count")
            render_bar_chart(df_tipo.sort_values("count", ascending=False), "count", "prov_type", DIM_TYPE, "Segment Mix")
    with s3:
        if "prov_name" in df_providers.columns:
            df_name = df_providers.groupby("prov_name").size().reset_index(name="count")
            render_bar_chart(df_name.sort_values("count", ascending=False).head(10), "count", "prov_name", DIM_NAME, "Entity Ranking")
