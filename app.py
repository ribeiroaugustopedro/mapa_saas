import pandas as pd
import numpy as np
import streamlit as st
import folium
from folium import LayerControl
from folium.plugins import HeatMap, MarkerCluster
from modules.data import load_all_data
from modules.utils import generate_filters, haversine_vectorized, identify_nearby_region
from modules.map_builder import create_base_map, add_heatmap, add_provider_markers, apply_layers, render_map_stable, render_map_interactive
from modules.dashboard import render_member_dashboard, render_provider_dashboard, calculate_full_point_metrics
from modules.agent_ai import render_ai_advisor

st.set_page_config(page_title="Network Planner | Intelligence Terminal", layout="wide", initial_sidebar_state="expanded")

with open(".streamlit/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 1. State Initialization
if "ping_location" not in st.session_state: st.session_state["ping_location"] = None
if "simulation_result" not in st.session_state: st.session_state["simulation_result"] = None
if "trigger_simulation" not in st.session_state: st.session_state["trigger_simulation"] = False
if "trigger_capture" not in st.session_state: st.session_state["trigger_capture"] = False
if "captured_image" not in st.session_state: st.session_state["captured_image"] = None
if "show_provider_markers" not in st.session_state: st.session_state["show_provider_markers"] = True
if "cluster_markers" not in st.session_state: st.session_state["cluster_markers"] = True
if "manual_pin_enabled" not in st.session_state: st.session_state["manual_pin_enabled"] = False

# 2. Data Load & Pre-process
df_users, df_providers, sidebar_config, config_portfolio = load_all_data()
df_users_filtered = df_users.copy()
df_providers_filtered = df_providers.copy()

# 3. Sidebar UI
tab_filtros, tab_ai = st.sidebar.tabs(["Filters", "AI Assistant"])

with tab_filtros:
    if st.button("Reset System", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("##### System & Display")
    with st.expander("MAP CONFIGURATION", expanded=False):
        theme_map = st.selectbox("Map Theme", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"], key="map_type")
        st.toggle("Freeze Viewport", value=False, key="locked_mode")
        if st.button("Capture Analytics", use_container_width=True):
            st.session_state["trigger_capture"] = True
            st.rerun()

    if st.session_state.get("trigger_capture"):
        st.session_state["trigger_capture"] = False
        st.components.v1.html("<script>setTimeout(function(){ window.print(); }, 500);</script>", height=0)

    map_modes = st.multiselect("Active Layers", ["Heatmap", "Coverage Radius"], key="map_modes")
    
    st.divider()
    
    def on_change_manual():
        if not st.session_state.get("manual_pin_enabled"):
            st.session_state["ping_location"] = None

    st.markdown("##### Intelligence & Analysis")
    c_i1, c_i2 = st.columns(2)
    with c_i1:
        st.toggle("Manual Point", key="manual_pin_enabled", on_change=on_change_manual)
    with c_i2:
        if st.session_state.get("manual_pin_enabled") and st.session_state.get("ping_location"):
            if st.button("Remove Point", use_container_width=True):
                st.session_state["ping_location"] = None
                st.rerun()
            
    c_a1, c_a2 = st.columns(2)
    with c_a1:
        if st.button("Optimized Search", use_container_width=True):
            st.session_state["trigger_simulation"] = True
    with c_a2:
        if st.session_state.get("simulation_result"):
            if st.button("Clear Result", use_container_width=True):
                st.session_state["simulation_result"] = None
                st.rerun()
            
    radius_km = st.slider("Search Radius (km)", 0, 20, 0, key="radius_km")
    
    st.divider()
    
    st.markdown("##### Visibility & Tools")
    st.toggle("Show Points", key="show_provider_markers")
    st.toggle("Clustering", key="cluster_markers")
    
    st.divider()
    
    st.markdown("##### Targeted Filters")
    with st.expander("PROVIDERS FILTERS", expanded=False):
        if "prov_name" in df_providers.columns:
            opts = sorted(df_providers["prov_name"].dropna().astype(str).unique())
            st.multiselect("Name", options=opts, key="busca_prestador")
        df_providers_filtered = generate_filters(df_providers_filtered, st, sidebar_config, key_prefix="sidebar_tab")
    
    with st.expander("USERS FILTERS", expanded=False):
        df_users_filtered = generate_filters(df_users_filtered, st, config_portfolio, key_prefix="expander_users_auto")

# 4. Filter Post-Processing
if st.session_state.get("busca_prestador"):
    df_p_name = df_providers[df_providers["prov_name"].isin(st.session_state["busca_prestador"])]
    df_providers_filtered = pd.concat([df_providers_filtered, df_p_name]).drop_duplicates(subset=["prov_id"])

# 4.5 Simulation Processing
if st.session_state.get("trigger_simulation"):
    if not df_users_filtered.empty:
        st.session_state["simulation_result"] = {
            "lat": df_users_filtered["loc_latitude"].mean(), 
            "lon": df_users_filtered["loc_longitude"].mean()
        }
    st.session_state["trigger_simulation"] = False
    st.rerun()

# 5. Main View Logic
t_map, t_providers, t_portfolio = st.tabs(["Map", "Providers", "Users"])

with t_map:
    st.markdown("<h2 style='text-align: center; font-size: 1.25rem;'>Network Map</h2>", unsafe_allow_html=True)
    
    manual_on = st.session_state.get("manual_pin_enabled", False)
    mapa = create_base_map(st.session_state.get("map_type", "OpenStreetMap"), locked=st.session_state.get("locked_mode", False), minimalist=manual_on)
    
    apply_layers(
        mapa, df_providers_filtered, df_users_filtered, 
        show_h="Heatmap" in st.session_state.get("map_modes", []), 
        show_m=st.session_state.get("show_provider_markers", True), 
        show_r="Coverage Radius" in st.session_state.get("map_modes", []), 
        cluster_m=st.session_state.get("cluster_markers", True), 
        rad=st.session_state.get("radius_km", 0), 
        ping_loc=st.session_state.get("ping_location"), 
        best_pt=st.session_state.get("simulation_result")
    )
    
    if manual_on:
        res = render_map_interactive(mapa, key=f"v_map_inter_{manual_on}")
        if res and res.get("last_clicked"):
            if res["last_clicked"] != st.session_state.get("ping_location"):
                st.session_state["ping_location"] = res["last_clicked"]
                st.rerun()
    else:
        render_map_stable(mapa)

with t_portfolio:
    render_member_dashboard(df_users_filtered)

with t_providers:
    render_provider_dashboard(df_providers_filtered)

with tab_ai:
    render_ai_advisor(df_users_filtered, df_providers_filtered)
