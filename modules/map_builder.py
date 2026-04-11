import folium
import streamlit as st
import pandas as pd
import numpy as np
from folium import FeatureGroup, LayerControl
from folium.plugins import (
    Draw, Fullscreen, Geocoder, HeatMap, LocateControl, 
    MiniMap, MeasureControl, MousePosition, FastMarkerCluster
)
from streamlit_folium import st_folium
from folium.features import DivIcon

# --- DESIGN SYSTEM ---
MAP_HEIGHT = 600

MAPPING_TYPES = {
    "GENERAL HOSPITAL": {"icon": "building", "color": "blue", "hex": "#1e40af"},
    "EMERGENCY CENTER": {"icon": "ambulance", "color": "darkred", "hex": "#991b1b"},
    "PRIVATE CLINIC": {"icon": "user-md", "color": "cadetblue", "hex": "#2a9d8f"},
    "WOMENS AND CHILDREN": {"icon": "child", "color": "pink", "hex": "#ec4899"},
    "SPECIALTY MEDICAL": {"icon": "stethoscope", "color": "orange", "hex": "#f59e0b"},
    "LOCATION POINT": {"icon": "crosshairs", "color": "red", "hex": "#ef4444"},
    "AI RECOMMENDATION": {"icon": "bullseye", "color": "green", "hex": "#22c55e"},
    "DEFAULT": {"icon": "info-circle", "color": "gray", "hex": "#64748b"}
}

def get_cfg(row):
    t = str(row.get("prov_type", "")).upper().strip()
    for k, v in MAPPING_TYPES.items():
        if k in t: return v
    return MAPPING_TYPES["DEFAULT"]

def _get_impact_html(lat, lon, m_df, rad, total_count=0):
    if m_df.empty or not rad: return ""
    from modules.utils import haversine_vectorized
    
    dists = haversine_vectorized(lon, lat, m_df["loc_longitude"].values, m_df["loc_latitude"].values)
    in_range = m_df[dists <= rad]
    count = len(in_range)
    total = total_count if total_count > 0 else len(m_df)
    share = (count / total * 100) if total > 0 else 0
    
    return f"""
    <div style='margin-top:10px; border-top: 1px solid #e2e8f0; padding-top: 10px;'>
        <b style='color:#1e293b; font-size:11px; letter-spacing:0.02em; text-transform:uppercase;'>Impact Area ({rad}km)</b>
        <div style='display:flex; justify-content:space-between; margin-top:6px;'>
            <span style='font-size:12px; color:#64748b;'>Users Coverage:</span>
            <span style='font-size:12px; font-weight:700; color:#0f172a;'>{count:,} ({share:.1f}%)</span>
        </div>
    </div>
    """

def get_popup_content(row, radius_km=None, total_users=None, m_df=None, title="Provider"):
    p_type = str(row.get("prov_type", "Manual")).upper().strip()
    cfg = get_cfg(row) if "prov_type" in row else {"icon": "crosshairs", "hex": "#ef4444"}
    
    info = ""
    fields = [("Status", "prov_status"), ("Region", "loc_region"), ("State", "loc_state"), ("City", "loc_city")]
    
    for label, col in fields:
        if col in row:
            value = row[col]
            if pd.notna(value) and str(value).strip().lower() not in ("", "-", "nan"):
                info += f"<div style='margin-bottom:4px;'><b style='color:#64748b; font-size:10px;'>{label.upper()}:</b> <span style='font-size:11px; color:#334155;'>{value}</span></div>"
    
    impact = ""
    lat_val = row.get("loc_latitude") or row.get("lat")
    lon_val = row.get("loc_longitude") or row.get("lon")
    if radius_km and m_df is not None and lat_val and lon_val:
        impact = _get_impact_html(lat_val, lon_val, m_df, radius_km, total_users)
    
    nome = row.get("prov_name", title)
    coords_text = f"({lat_val:.4f}, {lon_val:.4f})" if pd.notna(lat_val) and pd.notna(lon_val) else ""
    
    return f"""
    <div style='font-family: "Inter", sans-serif; min-width: 240px; padding: 2px;'>
        <div style='display: flex; align-items: center; border-bottom: 3px solid {cfg["hex"]}; padding-bottom: 10px; margin-bottom: 12px;'>
            <div style='background: {cfg["hex"]}; color: white; border-radius: 10px; width: 52px; height: 32px; display: flex; align-items: center; justify-content: center; margin-right: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                <i class='fa fa-{cfg["icon"]}' style='font-size: 18px;'></i>
            </div>
            <div style='font-weight: 800; font-size: 15px; color: #0f172a; line-height: 1.1;'>{nome[:30]}</div>
        </div>
        <div style='padding:0 2px;'>
            {info}
            {impact}
        </div>
        <div style='margin-top:14px; padding-top:8px; border-top: 1px dashed #e2e8f0; font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700; letter-spacing:0.02em;'>
            {p_type} <span style='font-weight:400; color:#cbd5e1; margin-left:4px;'>{coords_text}</span>
        </div>
    </div>
    """

def create_base_map(map_theme="OpenStreetMap", locked=False, lat=37.0902, lon=-95.7129, minimalist=False):
    options = {"zoomControl": True, "scrollWheelZoom": not locked, "dragging": not locked}
    m = folium.Map(location=[lat, lon], zoom_start=4, tiles=map_theme, prefer_canvas=True, height=MAP_HEIGHT, **options)
    
    m.get_root().add_child(folium.JavascriptLink("https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js"))
    m.get_root().add_child(folium.CssLink("https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css"))
    
    style_inject = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    <style>
        html, body { background-color: #0e1117 !important; margin: 0; padding: 0; }
        .leaflet-popup-content-wrapper { border-radius: 12px !important; padding: 0 !important; overflow: hidden !important; }
        .leaflet-popup-content { margin: 0 !important; width: auto !important; padding: 12px !important; font-family: 'Inter', sans-serif !important; }
        .leaflet-popup-tip-container { display: none !important; }
        .leaflet-container { 
            font-family: 'Inter', sans-serif !important; 
            background: #0e1117 !important; 
            outline: none !important;
            border: none !important;
            box-shadow: none !important;
        }
        .leaflet-container:focus { outline: none !important; border: none !important; }
        .leaflet-control-mouseposition { 
            background-color: rgba(255, 255, 255, 0.9) !important;
            padding: 5px 15px !important;
            border-radius: 8px !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            border: 1px solid #e2e8f0 !important;
            margin-bottom: 10px !important;
            margin-left: 10px !important;
            color: #1e293b !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        }
    </style>
    """
    m.get_root().header.add_child(folium.Element(style_inject))
    
    if not locked:
        if not minimalist:
            # Command Suite (Left Toolbar)
            Fullscreen(position='topleft').add_to(m)
            LocateControl(position='topleft', keepCurrentZoomLevel=True).add_to(m)
            Draw(position='topleft').add_to(m)
            MeasureControl(position='topleft', primary_length_unit="kilometers", dec_point=',', thousands_sep='.').add_to(m)
            Geocoder(position='topright').add_to(m)
            
            # Natural Positioning (Bottom)
            MiniMap(position='bottomright', width=150, height=150, toggle_display=True).add_to(m)
            MousePosition(position='bottomleft', separator=' | ', prefix="coord: ", lng_first=False, num_digits=4).add_to(m)
                
    return m

def add_provider_markers(mapa, df_providers, radius_km=None, total_users=None, m_df=None, cluster_markers=True):
    if df_providers.empty: return
    provider_data = []
    for i, row in df_providers.iterrows():
        lat, lon = row.get("loc_latitude"), row.get("loc_longitude")
        if pd.isna(lat) or pd.isna(lon): continue
        name = str(row.get("prov_name", "Provider"))
        popup_html = get_popup_content(row, radius_km, total_users, m_df=m_df)
        cfg = get_cfg(row)
        provider_data.append([lat, lon, cfg["icon"], cfg["color"], name, popup_html, cfg["hex"]])
    
    if cluster_markers:
        callback = "function(r){var i; try{if(L.AwesomeMarkers && L.AwesomeMarkers.icon){i=L.AwesomeMarkers.icon({icon:r[2],markerColor:r[3],prefix:'fa'});}else{i=new L.Icon.Default();}}catch(e){i=new L.Icon.Default();} var m=L.marker(new L.LatLng(r[0],r[1]),{icon:i}); m.bindTooltip(r[4]); m.bindPopup(r[5]); return m;}"
        FastMarkerCluster(data=provider_data, callback=callback, name="Providers").add_to(mapa)
    else:
        fg = folium.FeatureGroup(name="Providers").add_to(mapa)
        for d in provider_data:
            folium.Marker(
                location=[d[0], d[1]],
                popup=folium.Popup(d[5], max_width=450),
                tooltip=d[4],
                icon=folium.Icon(color=d[3], icon=d[2], prefix='fa')
            ).add_to(fg)

def add_heatmap(mapa, df_heat):
    if df_heat.empty: return
    import duckdb
    try:
        agg = duckdb.query("SELECT ROUND(loc_latitude, 2) as lat, ROUND(loc_longitude, 2) as lon, COUNT(*) as p FROM df_heat WHERE loc_latitude IS NOT NULL GROUP BY 1, 2").to_df()
        if not agg.empty: HeatMap(agg[["lat", "lon", "p"]].values.tolist(), radius=22, blur=18, min_opacity=0.3).add_to(mapa)
    except: pass

def add_ping_marker(mapa, lat, lon, m_df, p_df, rad=None):
    from modules.utils import identify_nearby_region
    loc_info = identify_nearby_region(lat, lon, p_df) if not p_df.empty else {}
    
    row_manual = {
        "loc_latitude": lat, "loc_longitude": lon,
        "loc_region": loc_info.get("loc_region", "UNDEFINED"),
        "loc_state": loc_info.get("loc_state", "N/A"),
        "loc_city": loc_info.get("loc_city", "MANUAL ENTRY"),
        "prov_type": "LOCATION POINT",
        "prov_name": "MANUAL LOCATION"
    }
    
    popup_html = get_popup_content(row_manual, radius_km=rad, total_users=None, m_df=m_df, title="Manual Location")
    
    folium.Marker(
        location=[lat, lon], 
        icon=folium.Icon(color='red', icon='crosshairs', prefix='fa'),
        popup=folium.Popup(popup_html, max_width=400, show=True)
    ).add_to(mapa)
    
    if rad: folium.Circle(location=[lat, lon], radius=rad*1000, color="#ef4444", fill=True, fill_opacity=0.08, weight=1).add_to(mapa)

def add_simulation_marker(mapa, lat, lon, m_df, p_df, rad):
    from modules.utils import identify_nearby_region
    loc_info = identify_nearby_region(lat, lon, p_df) if not p_df.empty else {}
    
    row_sim = {
        "loc_latitude": lat, "loc_longitude": lon,
        "loc_region": loc_info.get("loc_region", "UNDEFINED"),
        "loc_state": loc_info.get("loc_state", "N/A"),
        "loc_city": loc_info.get("loc_city", "AI RECOMMENDED"),
        "prov_type": "AI RECOMMENDATION",
        "prov_name": "OPTIMIZED LOCATION"
    }
    
    popup_html = get_popup_content(row_sim, radius_km=rad, total_users=None, m_df=m_df, title="OPTIMIZED LOCATION")
    
    folium.Marker(
        location=[lat, lon], 
        icon=folium.Icon(color='green', icon='bullseye', prefix='fa'),
        popup=folium.Popup(popup_html, max_width=400, show=True)
    ).add_to(mapa)
    
    folium.Circle(location=[lat, lon], radius=rad*1000, color="#22c55e", fill=True, fill_opacity=0.1, weight=2).add_to(mapa)

def apply_layers(m_obj, p_df, m_df, show_h=False, show_m=True, show_r=False, cluster_m=True, rad=0, ping_loc=None, best_pt=None):
    if show_h: add_heatmap(m_obj, m_df)
    if show_m:
        tm = m_df['user_id'].nunique() if 'user_id' in m_df.columns else len(m_df)
        add_provider_markers(m_obj, p_df, radius_km=rad, total_users=tm, m_df=m_df, cluster_markers=cluster_m)
    if ping_loc: add_ping_marker(m_obj, ping_loc["lat"], ping_loc["lng"], m_df, p_df, rad=rad)
    if best_pt: add_simulation_marker(m_obj, best_pt["lat"], best_pt["lon"], m_df, p_df, rad=rad)

def render_map_stable(mapa):
    html = mapa._repr_html_()
    # Add a 40px buffer to prevent plugin clipping at the base
    st.components.v1.html(html, height=MAP_HEIGHT + 40)
    return None

def render_map_interactive(mapa, key="inter_map"):
    # Add a 40px buffer to prevent plugin clipping at the base
    return st_folium(mapa, width=None, use_container_width=True, height=MAP_HEIGHT + 40, returned_objects=["last_clicked"], key=key)
