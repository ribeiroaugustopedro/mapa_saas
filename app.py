import streamlit as st
import pandas as pd
from pathlib import Path
import datetime
import json
import os

from modules.data import get_data
from modules.utils import (
    generate_filters, detect_filter_columns, find_optimal_point, 
    save_map_as_image
)
from modules.map_builder import (
    create_base_map, 
    add_provider_markers, 
    add_heatmap, 
    render_map,
    add_ping_marker,
    add_simulation_marker
)
from modules.dashboard import (
    render_member_dashboard, 
    render_provider_dashboard,
    calculate_member_count_in_radius, 
    calculate_full_point_metrics,
    identify_nearby_region,
    get_theme_colors
)
from modules.data import get_data, get_filtered_heatmap_grid
from modules.agent_ai import generate_data_summary, ask_agent


st.set_page_config(layout="wide", page_title="Network Map")

css_path = Path(__file__).parent / ".streamlit" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Robust Session State Initialization
INIT_KEYS = {
    "ping_location": None,
    "trigger_printscreen": False,
    "last_capture_info": None,
    "simulation_result": None,
    "simulation_benchmark": None,
    "show_provider_markers": True,
    "cluster_markers": True,
    "manual_pin_enabled": False
}

for key, val in INIT_KEYS.items():
    if key not in st.session_state:
        st.session_state[key] = val

try:
    df_providers, df_members = get_data()
except Exception as e:
    st.error(f"Error loading base data: {str(e)}")
    df_providers, df_members = pd.DataFrame(), pd.DataFrame()


if df_providers.empty:
    st.warning("Data not loaded. Please check files in 'dataset' folder.")
    st.stop()

# --- Data Initialization & Filter Discovery ---
df_providers_filtered = df_providers.copy()
df_members_filtered = df_members.copy()

cfg_ignore_providers = ["prov_id", "loc_latitude", "loc_longitude", "loc_zip_code", "prov_name", "prov_tax_id", "loc_neighborhood", "neighborhood"]
sidebar_config = detect_filter_columns(df_providers_filtered, ignored_columns=cfg_ignore_providers)

IGNORE_MEMBERS = ["member_id", "loc_zip_code", "loc_latitude", "loc_longitude", "user_id", "loc_neighborhood", "neighborhood"]
config_members = detect_filter_columns(df_members_filtered, ignored_columns=IGNORE_MEMBERS)

tab_filtros, tab_ai = st.sidebar.tabs(["Filters", "AI Assistant"])

with tab_filtros:
    if st.button("Reset", use_container_width=True, help="Remove all filters and restore the map."):
        for key in list(st.session_state.keys()):
            if key.startswith("sidebar_tab_") or key.startswith("expander_carteira_auto_"):
                del st.session_state[key]
        st.rerun()

    with st.expander("System Configuration", expanded=False):
        map_type = st.selectbox("Map Theme", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"], key="map_type")
        locked_mode = st.toggle("Freeze Map (Print)", value=False, key="locked_mode")
        if st.button("Capture View", use_container_width=True):
            st.session_state["trigger_printscreen"] = True
            st.rerun()

        if st.session_state.get("last_capture_info"):
            ci = st.session_state["last_capture_info"]
            st.success("Analysis captured!")
            with open(ci["path"], "rb") as f:
                st.download_button(f"Download {ci['filename']}", data=f, file_name=ci['filename'], use_container_width=True)
            if st.button("Clear Capture", use_container_width=True):
                st.session_state["last_capture_info"] = None
                st.rerun()

    st.markdown("### Visualization Analysis")
    if st.session_state.get("ping_location"):
        if st.button("Remove Manual Pin", use_container_width=True):
            st.session_state["ping_location"] = None
            st.rerun()
    map_modes = st.multiselect("Layers", ["Heatmap (Member Portfolio)", "Coverage Radius"], key="map_modes")
    radius_km = st.slider("Radius (km)", 0, 20, 0, key="radius_km")
    
    st.markdown("### Geo Simulation")
    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        if st.button("Search Optimized", use_container_width=True):
            st.session_state["trigger_simulation"] = True
    with col_meta2:
        if st.button("Clear Results", use_container_width=True):
            st.session_state["simulation_result"] = None
            st.rerun()

    st.markdown("### Network Management")
    st.toggle("Show Provider Pins", key="show_provider_markers")
    st.toggle("Enable Clustering", key="cluster_markers")
    st.toggle("Enable Manual Pin", key="manual_pin_enabled")

    # Network Filters
    if "prov_name" in df_providers.columns:
        opcoes_busca = sorted(df_providers["prov_name"].dropna().astype(str).unique())
        busca_multi = st.multiselect("Direct Search", options=opcoes_busca, key="busca_prestador")
    else:
        busca_multi = []

    with st.expander("Provider Filters", expanded=False):
        df_providers_filtered = generate_filters(df_providers_filtered, st, sidebar_config, key_prefix="sidebar_tab")

    if busca_multi:
        df_providers_name_filtered = df_providers[df_providers["prov_name"].isin(busca_multi)]
        # Check for active categorical filters
        active_cat_filters = any(st.session_state.get(f"sidebar_tab_{c['col']}") for c in sidebar_config)
        if active_cat_filters:
            df_providers_filtered = pd.concat([df_providers_filtered, df_providers_name_filtered]).drop_duplicates(subset=["prov_id"])
        else:
            df_providers_filtered = df_providers_name_filtered

    st.markdown("### Member Portfolio")
    with st.expander("Member Filters", expanded=False):
        df_members_filtered = generate_filters(df_members_filtered, st, config_members, key_prefix="expander_members_auto")

# Helper for consistent map layer application
def apply_map_layers(m_obj, providers_df, members_df, show_h=False, show_m=True, show_r=False, cluster_m=True, rad=0, ping_loc=None, best_pt=None):
    if show_h:
        add_heatmap(m_obj, members_df, count_unique=True)
    
    if show_m:
        id_col = 'user_id' if 'user_id' in members_df.columns else 'member_id'
        total_m = members_df[id_col].nunique() if id_col in members_df.columns else len(members_df)
        add_provider_markers(
            m_obj, providers_df, 
            radius_km=rad, total_portfolio=total_m, 
            show_radius=show_r, cluster_markers=cluster_m
        )
    
    if ping_loc:
        lat_p, lon_p = ping_loc["lat"], ping_loc["lng"]
        m_ping = calculate_full_point_metrics(lat_p, lon_p, members_df, rad)
        addr_p = identify_nearby_region(lat_p, lon_p, members_df)
        add_ping_marker(
            m_obj, lat_p, lon_p, 
            info=f"<b>Coordinates:</b> {lat_p:.4f}, {lon_p:.4f}<br>",
            radius_km=rad if show_r else None, 
            metrics=m_ping, address_info=addr_p
        )
            
    if best_pt:
        lat_o, lon_o, count_o = best_pt
        m_opt = calculate_full_point_metrics(lat_o, lon_o, members_df, rad)
        addr_o = identify_nearby_region(lat_o, lon_o, members_df)
        add_simulation_marker(
            m_obj, lat_o, lon_o, count_o, rad,
            best_e=st.session_state.get("simulation_benchmark"),
            metric_name=st.session_state.get("simulation_metric_label", ""),
            metrics=m_opt, address_info=addr_o
        )

show_heatmap_members = "Heatmap (Member Portfolio)" in map_modes
show_radius = "Coverage Radius" in map_modes

if radius_km > 0 and not df_providers_filtered.empty:
    with st.spinner("Updating coverage statistics..."):
        radius_counts = calculate_member_count_in_radius(df_providers_filtered, df_members_filtered, radius_km)
else:
    radius_counts = {}

# Coordinate and Zoom preparation
if st.session_state.get("last_map_center") and st.session_state.get("last_map_zoom"):
    lat_center, lon_center = st.session_state["last_map_center"]["lat"], st.session_state["last_map_center"]["lng"]
    zoom_level = st.session_state["last_map_zoom"]
else:
    try:
        provider_lats = df_providers_filtered["loc_latitude"].dropna() if not df_providers_filtered.empty else pd.Series()
        member_lats = df_members_filtered["loc_latitude"].dropna() if not df_members_filtered.empty else pd.Series()
        all_lats = pd.concat([provider_lats, member_lats])
        
        provider_lons = df_providers_filtered["loc_longitude"].dropna() if not df_providers_filtered.empty else pd.Series()
        member_lons = df_members_filtered["loc_longitude"].dropna() if not df_members_filtered.empty else pd.Series()
        all_lons = pd.concat([provider_lons, member_lons])
        
        if not all_lats.empty and not all_lons.empty:
            lat_center, lon_center = all_lats.mean(), all_lons.mean()
            max_diff = max(all_lats.max() - all_lats.min(), all_lons.max() - all_lons.min())
            zoom_level = 4 if max_diff > 30 else 5 if max_diff > 15 else 8 if max_diff > 5 else 10
        else:
            lat_center, lon_center, zoom_level = 39.8283, -98.5795, 4 # Failsafe
    except:
        lat_center, lon_center, zoom_level = 39.8283, -98.5795, 4

# Simulation execution
if st.session_state.get("trigger_simulation") and not df_members_filtered.empty:
    with st.spinner("Simulating suggested center..."):
        best_new_point, best_existing_point = find_optimal_point(
            df_members_filtered, radius_km, 
            df_providers=df_providers_filtered, count_unique=True
        )
        st.session_state.update({
            "simulation_result": best_new_point,
            "simulation_benchmark": best_existing_point,
            "simulation_metric_label": "Portfolio Volume",
            "trigger_simulation": False
        })

# --- Main Operational Interface ---
tab_map, tab_members, tab_providers = st.tabs(["Map", "Members", "Providers"])

with tab_map:
    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 700; color: {get_theme_colors()['title']};'>Network Map</h2>", unsafe_allow_html=True)
    
    # Map Object Construction
    mapa = create_base_map(lat_center, lon_center, map_type, zoom_start=zoom_level, locked=locked_mode)

    df_providers_for_map = df_providers_filtered.copy()
    if radius_counts and "prov_id" in df_providers_for_map.columns:
        df_providers_for_map["beneficiarios_no_raio_dinamico"] = df_providers_for_map["prov_id"].map(radius_counts)

    # Performance Optimization: SQL-based Gridded Heatmap
    # Extract filters from state for SQL optimization
    sql_filter = "1=1"
    active_regions = st.session_state.get("expander_members_auto_loc_region", [])
    if active_regions:
        regs = "', '".join([str(r).upper() for r in active_regions])
        sql_filter += f" AND UPPER(loc_region) IN ('{regs}')"
    
    df_heat_grid = get_filtered_heatmap_grid(sql_filter)

    apply_map_layers(
        mapa, df_providers_for_map, df_heat_grid,
        show_h=show_heatmap_members, 
        show_m=st.session_state.get("show_provider_markers", True), 
        show_r=show_radius,
        cluster_m=st.session_state.get("cluster_markers", True), 
        rad=radius_km, 
        ping_loc=st.session_state.get("ping_location"),
        best_pt=st.session_state.get("simulation_result")
    )

    # High-Persistence Native HTML Rendering (Bypasses st_folium instability)
    import streamlit.components.v1 as components
    map_html = mapa._repr_html_()
    components.html(map_html, height=700)
    
    # Minimal state tracking for simulation
    map_data = None 

# Capture Logic (Global Process)
if st.session_state.get("trigger_printscreen"):
    center = st.session_state.get("last_map_center", {"lat": lat_center, "lng": lon_center})
    zoom = st.session_state.get("last_map_zoom", zoom_level)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"printscreens/network_map_{timestamp}.png"
    
    with st.spinner("Rendering map image..."):
        m_print = create_base_map(center["lat"], center["lng"], map_type, zoom_start=zoom, locked=True)
        apply_map_layers(
            m_print, df_providers_for_map, df_members_filtered,
            show_h=show_heatmap_members, 
            show_m=st.session_state["show_provider_markers"], 
            show_r=show_radius,
            cluster_m=st.session_state["cluster_markers"], 
            rad=radius_km,
            ping_loc=st.session_state.get("ping_location"),
            best_pt=st.session_state.get("simulation_result")
        )
        capture_success = save_map_as_image(m_print, filepath)
        
    if capture_success:
        st.session_state["last_capture_info"] = {
            "path": filepath,
            "filename": f"Network_Map_{timestamp}.png"
        }
    else:
        st.error("Technical error generating capture.")
    
    st.session_state["trigger_printscreen"] = False
    st.rerun()



with tab_members:
    render_member_dashboard(df_members_filtered)

with tab_providers:
    render_provider_dashboard(df_providers_filtered)


with tab_ai:
    @st.fragment
    def ai_fragment():
        st.markdown('''
            <div style="padding-bottom: 0.5rem; margin-bottom: 0.5rem;">
                <p style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-primary); font-weight: 700; text-transform: uppercase; letter-spacing: 0.2em; margin:0;">
                    Strategic Advisory
                </p>
            </div>
        ''', unsafe_allow_html=True)

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Minimalist Control and Suggestions
        if not st.session_state.messages:
            sug_cols = st.columns(2)
            with sug_cols[0]:
                if st.button("Density Gaps?", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "Where are the critical population density gaps without provider coverage?"})
                    st.rerun()
            with sug_cols[1]:
                if st.button("Expansion ROI?", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "Analyze the ROI of expanding to regions with higher Platinum product concentration."})
                    st.rerun()

        # Terminal Input
        user_input = st.chat_input("Query Strategy...")
        
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.rerun()

        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            # Discrete Loading Indicator
            status_placeholder = st.empty()
            status_placeholder.markdown('''
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 1rem;">
                    <div class="ai-icon-pulse" style="width: 8px; height: 8px;"></div>
                    <span style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.1em;">Analyzing Patterns...</span>
                </div>
            ''', unsafe_allow_html=True)

            data_context = generate_data_summary(
                df_providers_filtered, df_members_filtered,
                simulation_results=st.session_state.get("simulation_result"),
                benchmark_sim=st.session_state.get("simulation_benchmark"),
                radius_km=radius_km, map_modes=map_modes
            )
            # Inject Date for AI Precision
            now_str = datetime.datetime.now().strftime("%B %d, %Y")
            data_context += f"\n### System Date: {now_str}"
            
            response = ask_agent(st.session_state.messages[-1]["content"], data_context, history=st.session_state.messages[:-1])
            st.session_state.messages.append({"role": "assistant", "content": response})
            status_placeholder.empty()
            st.rerun()

        if st.session_state.messages:
            st.markdown("---")
            if st.button("Clear Logs", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
    
    ai_fragment()
