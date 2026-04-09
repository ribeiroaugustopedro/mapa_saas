import streamlit as st
import pandas as pd
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import io

# Local modules
from modules.data import get_data, get_filtered_heatmap_grid
from modules.utils import generate_filters, detect_filter_columns, find_optimal_point, capture_map_to_bytes
from modules.map_builder import create_base_map, add_provider_markers, add_heatmap, add_ping_marker, add_simulation_marker
from modules.dashboard import render_member_dashboard, render_provider_dashboard, calculate_member_count_in_radius, calculate_full_point_metrics, identify_nearby_region, get_theme_colors
from modules.agent_ai import generate_data_summary, ask_agent

st.set_page_config(layout="wide", page_title="Network Map")

css_path = Path(__file__).parent / ".streamlit" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

INIT_KEYS = {
    "ping_location": None,
    "trigger_capture": False,
    "captured_image": None,
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
    st.error(f"Error loading data: {str(e)}")
    df_providers, df_members = pd.DataFrame(), pd.DataFrame()

if df_providers.empty or df_members.empty:
    st.warning("⚠️ Data source not found or empty. Please check your MotherDuck token in Streamlit Secrets.")
    st.info("Ensure you have added `[motherduck]` and `MOTHERDUCK_TOKEN = '...'` to the Cloud Secrets dashboard.")
    st.stop()

df_providers_filtered = df_providers.copy()
df_members_filtered = df_members.copy()

cfg_ignore = ["prov_id", "loc_latitude", "loc_longitude", "loc_zip_code", "prov_name", "prov_tax_id", "loc_neighborhood", "neighborhood"]
sidebar_config = detect_filter_columns(df_providers_filtered, ignored_columns=cfg_ignore)

IGNORE_M = ["member_id", "loc_zip_code", "loc_latitude", "loc_longitude", "user_id", "loc_neighborhood", "neighborhood"]
config_members = detect_filter_columns(df_members_filtered, ignored_columns=IGNORE_M)

tab_filtros, tab_ai = st.sidebar.tabs(["Filters", "AI Assistant"])

with tab_filtros:
    if st.button("Reset", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("sidebar_tab_") or key.startswith("expander_members_auto"):
                del st.session_state[key]
        st.rerun()

    with st.expander("System Configuration", expanded=False):
        map_type = st.selectbox("Map Theme", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"], key="map_type")
        locked_mode = st.toggle("Freeze Map", value=False, key="locked_mode")
        if st.button("Capture View", use_container_width=True):
            st.session_state["trigger_capture"] = True
            st.rerun()

        if st.session_state.get("captured_image"):
            st.success("Capture ready for download")
            st.download_button("Download Capture", data=st.session_state["captured_image"], file_name="network_analysis.png", mime="image/png", use_container_width=True)
            if st.button("Clear Capture", use_container_width=True):
                st.session_state["captured_image"] = None
                st.rerun()

    if st.session_state.get("ping_location"):
        if st.button("Remove Manual Pin", use_container_width=True):
            st.session_state["ping_location"] = None
            st.rerun()
            
    map_modes = st.multiselect("Layers", ["Heatmap", "Coverage Radius"], key="map_modes")
    radius_km = st.slider("Radius (km)", 0, 20, 0, key="radius_km")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Search Optimized", use_container_width=True):
            st.session_state["trigger_simulation"] = True
    with col2:
        if st.button("Clear Results", use_container_width=True):
            st.session_state["simulation_result"] = None
            st.rerun()

    st.toggle("Show Provider Pins", key="show_provider_markers")
    st.toggle("Enable Clustering", key="cluster_markers")
    st.toggle("Enable Manual Pin", key="manual_pin_enabled")

    if "prov_name" in df_providers.columns:
        opts = sorted(df_providers["prov_name"].dropna().astype(str).unique())
        busca = st.multiselect("Direct Search", options=opts, key="busca_prestador")
    else:
        busca = []

    with st.expander("Provider Filters", expanded=False):
        df_providers_filtered = generate_filters(df_providers_filtered, st, sidebar_config, key_prefix="sidebar_tab")

    if busca:
        df_p_name = df_providers[df_providers["prov_name"].isin(busca)]
        df_providers_filtered = pd.concat([df_providers_filtered, df_p_name]).drop_duplicates(subset=["prov_id"])

    with st.expander("Member Filters", expanded=False):
        df_members_filtered = generate_filters(df_members_filtered, st, config_members, key_prefix="expander_members_auto")

def apply_layers(m_obj, p_df, m_df, show_h=False, show_m=True, show_r=False, cluster_m=True, rad=0, ping_loc=None, best_pt=None):
    if show_h:
        add_heatmap(m_obj, m_df, count_unique=True)
    if show_m:
        id_col = 'user_id' if 'user_id' in m_df.columns else 'member_id'
        tm = m_df[id_col].nunique() if id_col in m_df.columns else len(m_df)
        add_provider_markers(m_obj, p_df, radius_km=rad, total_portfolio=tm, show_radius=show_r, cluster_markers=cluster_m)
    if ping_loc:
        lp, ln = ping_loc["lat"], ping_loc["lng"]
        m_ping = calculate_full_point_metrics(lp, ln, m_df, rad)
        addr_p = identify_nearby_region(lp, ln, m_df)
        add_ping_marker(m_obj, lp, ln, info=f"Coordinates: {lp:.4f}, {ln:.4f}", radius_km=rad if show_r else None, metrics=m_ping, address_info=addr_p)
    if best_pt:
        lo, lno, co = best_pt
        m_opt = calculate_full_point_metrics(lo, lno, m_df, rad)
        addr_o = identify_nearby_region(lo, lno, m_df)
        add_simulation_marker(m_obj, lo, lno, co, rad, best_e=st.session_state.get("simulation_benchmark"), metrics=m_opt, address_info=addr_o)

show_h = "Heatmap" in map_modes
show_r = "Coverage Radius" in map_modes

radius_counts = calculate_member_count_in_radius(df_providers_filtered, df_members_filtered, radius_km) if radius_km > 0 and not df_providers_filtered.empty else {}

if st.session_state.get("trigger_simulation") and not df_members_filtered.empty:
    best_n, best_e = find_optimal_point(df_members_filtered, radius_km, df_providers=df_providers_filtered, count_unique=True)
    st.session_state.update({"simulation_result": best_n, "simulation_benchmark": best_e, "trigger_simulation": False})

tab_map, tab_members, tab_providers = st.tabs(["Map", "Members", "Providers"])

with tab_map:
    map_color = get_theme_colors()['title']
    st.markdown(f"<h2 style='font-family: var(--font-main); font-weight: 700; color: {map_color};'>Network Map</h2>", unsafe_allow_html=True)
    
    lats = pd.concat([df_providers_filtered["loc_latitude"], df_members_filtered["loc_latitude"]]).dropna()
    lons = pd.concat([df_providers_filtered["loc_longitude"], df_members_filtered["loc_longitude"]]).dropna()
    
    if not lats.empty:
        c_lat, c_lon = lats.mean(), lons.mean()
        diff = max(lats.max()-lats.min(), lons.max()-lons.min())
        z = 4 if diff > 30 else 5 if diff > 15 else 8 if diff > 5 else 10
    else:
        c_lat, c_lon, z = 39.8283, -98.5795, 4

    mapa = create_base_map(c_lat, c_lon, map_type, zoom_start=z, locked=locked_mode)
    df_p_map = df_providers_filtered.copy()
    if radius_counts and "prov_id" in df_p_map.columns:
        df_p_map["beneficiarios_no_raio_dinamico"] = df_p_map["prov_id"].map(radius_counts)

    sql_f = "1=1"
    apply_layers(mapa, df_p_map, get_filtered_heatmap_grid(sql_f), show_h=show_h, show_m=st.session_state.show_provider_markers, show_r=show_r, cluster_m=st.session_state.cluster_markers, rad=radius_km, ping_loc=st.session_state.ping_location, best_pt=st.session_state.simulation_result)
    
    import streamlit.components.v1 as components
    components.html(mapa._repr_html_(), height=700)

if st.session_state.get("trigger_capture"):
    with st.spinner("Initializing system capture (this may take a moment on first run)..."):
        try:
            # Lazy install playwright only when needed
            if 'playwright_ready' not in st.session_state:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                st.session_state.playwright_ready = True
            
            img = capture_map_to_bytes(mapa)
            if img:
                st.session_state["captured_image"] = img
                st.session_state["trigger_capture"] = False
                st.rerun()
            else:
                st.error("Capture failed. Visual rendering engine not responding.")
        except Exception as e:
            st.error(f"Capture engine error: {str(e)}")
        finally:
            st.session_state["trigger_capture"] = False

with tab_members:
    render_member_dashboard(df_members_filtered)

with tab_providers:
    render_provider_dashboard(df_providers_filtered)

with tab_ai:
    @st.fragment
    def ai_fragment():
        st.markdown('<p style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-primary); font-weight: 700; text-transform: uppercase;">Strategic Advisory</p>', unsafe_allow_html=True)
        if "messages" not in st.session_state: st.session_state.messages = []
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        user_input = st.chat_input("Query...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.rerun()
        
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            ctx = generate_data_summary(df_providers_filtered, df_members_filtered, st.session_state.get("simulation_result"), st.session_state.get("simulation_benchmark"), radius_km, map_modes)
            res = ask_agent(st.session_state.messages[-1]["content"], ctx, history=st.session_state.messages[:-1])
            st.session_state.messages.append({"role": "assistant", "content": res})
            st.rerun()
            
    ai_fragment()
