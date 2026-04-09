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
    identify_nearby_region
)
from modules.agent_ai import generate_data_summary, ask_agent


st.set_page_config(layout="wide", page_title="Network Map")

css_path = Path(__file__).parent / ".streamlit" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "ping_location" not in st.session_state:
    st.session_state["ping_location"] = None
if "trigger_printscreen" not in st.session_state:
    st.session_state["trigger_printscreen"] = False
if "last_capture_info" not in st.session_state:
    st.session_state["last_capture_info"] = None
if "simulation_result" not in st.session_state:
    st.session_state["simulation_result"] = None
if "simulation_benchmark" not in st.session_state:
    st.session_state["simulation_benchmark"] = None

try:
    df_providers, df_members = get_data()
except Exception as e:
    st.error(f"Error loading base data: {str(e)}")
    df_providers, df_members = pd.DataFrame(), pd.DataFrame()


if df_providers.empty:
    st.warning("Data not loaded. Please check files in 'dataset' folder.")
    st.stop()

# --- Data Initialization & Filter Discovery ---
cfg_ignore_providers = ["prov_id", "loc_latitude", "loc_longitude", "loc_zip_code", "prov_name"]
sidebar_config = detect_filter_columns(df_providers, ignored_columns=cfg_ignore_providers)

IGNORE_MEMBERS = ["member_id", "loc_zip_code", "loc_latitude", "loc_longitude"]
config_members = detect_filter_columns(df_members, ignored_columns=IGNORE_MEMBERS)

df_providers_filtered = df_providers.copy()
df_members_filtered = df_members.copy()

tab_filtros, tab_ai = st.sidebar.tabs(["Filters", "AI Assistant"])

with tab_filtros:
    if st.button("Total Reset", use_container_width=True, help="Remove all filters and restore the map."):
        for key in list(st.session_state.keys()):
            if key.startswith("sidebar_tab_") or key.startswith("expander_carteira_auto_"):
                del st.session_state[key]
        st.rerun()

    with st.expander("Export & Style", expanded=False):
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

    st.markdown("### Analysis")
    if st.session_state["ping_location"]:
        if st.button("Remove Manual Pin", use_container_width=True):
            st.session_state["ping_location"] = None
            st.rerun()
    map_modes = st.multiselect("Layers", ["Heatmap (Member Portfolio)", "Coverage Radius"], key="map_modes")
    radius_km = st.slider("Radius (km)", 0, 20, 0, key="radius_km")
    
    st.markdown("### Geo-Simulation")
    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        if st.button("Search Optimized", use_container_width=True):
            st.session_state["trigger_simulation"] = True
    with col_meta2:
        if st.button("Clear Results", use_container_width=True):
            st.session_state["simulation_result"] = None
            st.rerun()

    st.markdown("---")
    st.markdown("### Provider Network")
    st.toggle("Show Provider Pins", value=True, key="show_provider_markers")
    st.toggle("Enable Clustering", value=True, key="cluster_markers")
    st.toggle("Enable Manual Pin", value=False, key="manual_pin_enabled")

    # Network Filters
    if "prov_name" in df_providers.columns:
        opcoes_busca = sorted(df_providers["prov_name"].dropna().astype(str).unique())
        busca_multi = st.multiselect("Direct Search", options=opcoes_busca, key="busca_prestador")
    else:
        busca_multi = []

    with st.expander("Network Filters", expanded=False):
        df_providers_filtered = generate_filters(df_providers_filtered, st, sidebar_config, key_prefix="sidebar_tab")

    if busca_multi:
        df_providers_name_filtered = df_providers[df_providers["prov_name"].isin(busca_multi)]
        # Check for active categorical filters
        active_cat_filters = any(st.session_state.get(f"sidebar_tab_{c['col']}") for c in sidebar_config)
        if active_cat_filters:
            df_providers_filtered = pd.concat([df_providers_filtered, df_providers_name_filtered]).drop_duplicates(subset=["prov_id"])
        else:
            df_providers_filtered = df_providers_name_filtered

    st.markdown("---")
    st.markdown("### Customer Base Filters")
    with st.expander("Portfolio Attributes", expanded=False):
        df_members_filtered = generate_filters(df_members_filtered, st, config_members, key_prefix="expander_members_auto")

# Helper for consistent map layer application
def apply_map_layers(m_obj, providers_df, members_df, show_h=False, show_m=True, show_r=False, cluster_m=True, rad=0, ping_loc=None, best_pt=None):
    if show_h:
        add_heatmap(m_obj, members_df, count_unique=True)
    
    if show_m:
        total_m = members_df['member_id'].nunique() if 'member_id' in members_df.columns else len(members_df)
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
elif not df_providers_filtered.empty:
    all_lats = pd.concat([df_providers_filtered["loc_latitude"], df_members_filtered["loc_latitude"]])
    all_lons = pd.concat([df_providers_filtered["loc_longitude"], df_members_filtered["loc_longitude"]])
    lat_center, lon_center = all_lats.mean(), all_lons.mean()
    
    max_diff = max(all_lats.max() - all_lats.min(), all_lons.max() - all_lons.min())
    zoom_level = 4 if max_diff > 30 else 5 if max_diff > 15 else 6 if max_diff > 10 else 8 if max_diff > 5 else 10
else:
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

# Map Object Construction
mapa = create_base_map(lat_center, lon_center, map_type, zoom_start=zoom_level, locked=locked_mode)

df_providers_for_map = df_providers_filtered.copy()
if radius_counts and "prov_id" in df_providers_for_map.columns:
    df_providers_for_map["beneficiarios_no_raio_dinamico"] = df_providers_for_map["prov_id"].map(radius_counts)

apply_map_layers(
    mapa, df_providers_for_map, df_members_filtered,
    show_h=show_heatmap_members, 
    show_m=st.session_state["show_provider_markers"], 
    show_r=show_radius,
    cluster_m=st.session_state["cluster_markers"], 
    rad=radius_km, 
    ping_loc=st.session_state["ping_location"],
    best_pt=st.session_state["simulation_result"]
)

map_data = render_map(mapa)

if map_data:
    if map_data.get("last_clicked"):
        clicked_loc = map_data["last_clicked"]
        if st.session_state.get("manual_pin_enabled", False):
            if st.session_state["ping_location"] != clicked_loc:
                st.session_state["ping_location"] = clicked_loc
                st.rerun()
    
    if map_data.get("zoom"): st.session_state["last_map_zoom"] = map_data["zoom"]
    if map_data.get("center"): st.session_state["last_map_center"] = map_data["center"]

# Capture Logic
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
            ping_loc=st.session_state["ping_location"],
            best_pt=st.session_state["simulation_result"]
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



st.markdown("---")
render_member_dashboard(df_members_filtered)
st.markdown("---")
render_provider_dashboard(df_providers_filtered)


with tab_ai:
    st.markdown('''
        <div class="ai-header">
            <div class="ai-icon-pulse"></div>
            <h3 style="margin:0">Strategic Consulting AI</h3>
        </div>
        <div class="ai-subtitle">
            Advanced neural engine specialized in healthcare network optimization and geospatial strategy. 
            Ask about density gaps, expansion ROI, or competitor proximity.
        </div>
    ''', unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Strategic Suggestions (Chips)
    st.markdown('<div style="margin-top: 1rem; margin-bottom: 0.5rem; font-size: 0.8rem; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Suggested Analysis</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    sug_prompt = None
    with c1:
        if st.button("Expansion Strategy", use_container_width=True, help="Analyze the best regions for new clinics."):
            sug_prompt = "Based on the current member density, where are the critical gaps where we should prioritize opening new specialty centers?"
    with c2:
        if st.button("Competitor Impact", use_container_width=True, help="Analyze network overlap."):
            sug_prompt = "Analyze the current provider distribution. Are there areas with high member volume but low provider coverage (potential deserts)?"

    # Handle Input
    if prompt := (st.chat_input("How can I assist with your network strategy today?") or sug_prompt):
        if sug_prompt: # If it came from a button, we append it to history first
            prompt = sug_prompt
            
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Neural Engine analyzing network patterns..."):
            data_context = generate_data_summary(
                df_providers_filtered, 
                df_members_filtered,
                simulation_results=st.session_state.get("simulation_result"),
                benchmark_sim=st.session_state.get("simulation_benchmark"),
                radius_km=radius_km,
                map_modes=map_modes
            )
            
            response = ask_agent(prompt, data_context, history=st.session_state.messages)
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            with st.chat_message("assistant"):
                st.markdown(response)
                st.rerun()
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Reset Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
