import pandas as pd
import numpy as np
import streamlit as st
import folium
from folium import LayerControl
from folium.plugins import HeatMap, MarkerCluster
from modules.data import load_all_data
from modules.utils import generate_filters
from modules.map_builder import create_base_map, add_heatmap, add_provider_markers, apply_layers, render_map
from modules.dashboard import render_member_dashboard, render_provider_dashboard, calculate_full_point_metrics, identify_nearby_region
from modules.agent_ai import render_ai_advisor
from modules.utils import haversine_vectorized

st.set_page_config(page_title="Network Planner | Portfolio View", layout="wide", initial_sidebar_state="expanded")

with open(".streamlit/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

df_portfolio, df_providers, sidebar_config, config_portfolio = load_all_data()
df_portfolio_filtered = df_portfolio.copy()
df_providers_filtered = df_providers.copy()

if "ping_location" not in st.session_state: st.session_state["ping_location"] = None
if "simulation_result" not in st.session_state: st.session_state["simulation_result"] = None
if "trigger_simulation" not in st.session_state: st.session_state["trigger_simulation"] = False
if "trigger_capture" not in st.session_state: st.session_state["trigger_capture"] = False
if "captured_image" not in st.session_state: st.session_state["captured_image"] = None
if "show_provider_markers" not in st.session_state: st.session_state["show_provider_markers"] = True
if "cluster_markers" not in st.session_state: st.session_state["cluster_markers"] = True
if "manual_pin_enabled" not in st.session_state: st.session_state["manual_pin_enabled"] = False

# Sidebar
tab_filtros, tab_ai = st.sidebar.tabs(["Filters", "AI Assistant"])

with tab_filtros:
    if st.button("Reset System", use_container_width=True):
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

    map_modes = st.multiselect("Active Layers", ["Heatmap", "Coverage Radius"], key="map_modes")
    
    st.divider()
    
    st.markdown("##### Intelligence & Analysis")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Search Optimized", use_container_width=True):
            st.session_state["trigger_simulation"] = True
    with c2:
        if st.button("Clear Results", use_container_width=True):
            st.session_state["simulation_result"] = None
            st.rerun()
            
    radius_km = st.slider("Search Radius (km)", 0, 20, 0, key="radius_km")
    
    st.divider()
    
    st.markdown("##### Visibility & Tools")
    st.toggle("Show Points", key="show_provider_markers")
    st.toggle("Clustering", key="cluster_markers")
    st.toggle("Manual Point", key="manual_pin_enabled")
    
    if st.session_state.get("ping_location"):
        if st.button("Remove Manual Point", use_container_width=True):
            st.session_state["ping_location"] = None
            st.rerun()
            
    st.divider()
    
    st.markdown("##### Targeted Filters")
    with st.expander("PROVIDERS FILTERS", expanded=False):
        if "prov_name" in df_providers.columns:
            opts = sorted(df_providers["prov_name"].dropna().astype(str).unique())
            st.multiselect("Name", options=opts, key="busca_prestador")
        df_providers_filtered = generate_filters(df_providers_filtered, st, sidebar_config, key_prefix="sidebar_tab")
    
    with st.expander("PORTFOLIO FILTERS", expanded=False):
        df_portfolio_filtered = generate_filters(df_portfolio_filtered, st, config_portfolio, key_prefix="expander_members_auto")

# Process Filters
if st.session_state.get("busca_prestador"):
    df_p_name = df_providers[df_providers["prov_name"].isin(st.session_state["busca_prestador"])]
    df_providers_filtered = pd.concat([df_providers_filtered, df_p_name]).drop_duplicates(subset=["prov_id"])

# Simulation
if st.session_state["trigger_simulation"]:
    if not df_portfolio_filtered.empty:
        st.session_state["simulation_result"] = {"lat": df_portfolio_filtered["loc_latitude"].mean(), "lon": df_portfolio_filtered["loc_longitude"].mean()}
    st.session_state["trigger_simulation"] = False

# Main Area
t_map, t_providers, t_portfolio = st.tabs(["Map", "Providers", "Portfolio"])

with t_map:
    st.markdown("<h2 style='text-align: center; font-size: 1.25rem;'>Network Map</h2>", unsafe_allow_html=True)
    mapa = create_base_map(st.session_state.get("map_type", "OpenStreetMap"), locked=st.session_state.get("locked_mode", False))
    show_h = "Heatmap" in map_modes
    show_r = "Coverage Radius" in map_modes
    
    apply_layers(mapa, df_providers_filtered, df_portfolio_filtered, show_h=show_h, show_m=st.session_state.show_provider_markers, show_r=show_r, cluster_m=st.session_state.cluster_markers, rad=radius_km, ping_loc=st.session_state.ping_location, best_pt=st.session_state.simulation_result)
    
    map_res = render_map(mapa)
    if st.session_state.manual_pin_enabled and map_res and map_res.get("last_clicked"):
        st.session_state["ping_location"] = map_res["last_clicked"]
        st.rerun()

with t_portfolio:
    render_member_dashboard(df_portfolio_filtered)

with t_providers:
    render_provider_dashboard(df_providers_filtered)

with tab_ai:
    render_ai_advisor(df_portfolio_filtered, df_providers_filtered)

if st.session_state.get("trigger_capture"):
    st.session_state["trigger_capture"] = False
    st.rerun()
