import folium
import pandas as pd
from folium import FeatureGroup, LayerControl
from folium.plugins import (
    Draw, Fullscreen, Geocoder, HeatMap, LocateControl, 
    MiniMap, MeasureControl, MousePosition, FastMarkerCluster
)
from streamlit_folium import st_folium
from folium.features import DivIcon

def get_popup_content(row, radius_km=None, total_portfolio=None, metrics=None):
    info = ""
    fields = [("Status", "prov_tax_id"), ("Type", "prov_type"), ("Region", "loc_region"), ("City", "loc_city"), ("Neighborhood", "loc_neighborhood"), ("ZIP Code", "loc_zip_code")]
    for label, col in fields:
        if col in row:
            value = row[col]
            if pd.notna(value) and str(value).strip().lower() not in ("", "-", "nan"):
                info += f"<b>{label}:</b> {value}<br>"
    if metrics and isinstance(metrics, dict) and radius_km:
        port = metrics.get('portfolio', 0)
        t_port = metrics.get('total_portfolio', total_portfolio if total_portfolio else 0)
        share_port = (port / t_port * 100) if t_port > 0 else 0
        info += (f"<div style='margin-top:8px; border-top: 1px solid #f0f0f0; padding-top: 8px;'><b style='color: #444;'>Within Radius ({radius_km} km):</b><br><table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'><tr><td><b>Portfolio:</b></td><td style='text-align:right'>{port:,} <span style='font-size:10px; color:#666'>/ {t_port:,} ({share_port:.1f}%)</span></td></tr></table></div>")
    nome = row.get("prov_name", "Provider")
    return f"<div style='font-family: Arial, sans-serif;'><div style='text-align: center; font-weight: bold; border-bottom: 1px solid #ccc; margin-bottom: 8px;'>{nome}</div>{info}</div>"

def create_base_map(map_theme="OpenStreetMap", locked=False, lat=36.5, lon=-93.0):
    options = {"zoomControl": False, "scrollWheelZoom": False, "dragging": False} if locked else {}
    m = folium.Map(location=[lat, lon], zoom_start=4, tiles=map_theme, prefer_canvas=True, **options)
    if not locked:
        # Step 1: Core planning tools first
        Fullscreen(position='topleft').add_to(m)
        Draw(position='topleft').add_to(m)
        Geocoder(position='topright').add_to(m)
        MiniMap(toggle_display=True, position='bottomright').add_to(m)
        MousePosition(position='bottomright').add_to(m)
        
        # Step 2: Utility controls LAST as requested
        LocateControl(position='topleft').add_to(m)
        MeasureControl(position='topleft', primary_length_unit="kilometers").add_to(m)
        
        # Step 3: Inject CSS + JS for icon parity (Bypass Iframe isolation)
        map_inject = """
        <style>
        .leaflet-control-measure, .leaflet-control-measure-toggle {
            width: 30px !important;
            height: 30px !important;
            background-size: 16px 16px !important;
            border-radius: 4px !important;
            padding: 0 !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        .leaflet-control-measure { background-color: white !important; border: none !important; }
        .leaflet-control-measure-toggle { background-position: center !important; border: none !important; }
        </style>
        <script>
        setTimeout(function() {
            var controls = document.querySelectorAll('.leaflet-control-measure, .leaflet-control-measure-toggle');
            controls.forEach(function(el) {
                el.style.width = '30px';
                el.style.height = '30px';
                el.style.backgroundSize = '16px 16px';
                el.style.borderRadius = '4px';
            });
        }, 1000);
        </script>
        """
        m.get_root().header.add_child(folium.Element(map_inject))
        
    return m

def add_provider_markers(mapa, df_providers, radius_km=None, total_portfolio=None, show_radius=False, cluster_markers=True):
    if df_providers.empty: return
    MAPPING_TYPES = {"GENERAL HOSPITAL": {"icon": "building", "color": "blue"}, "EMERGENCY CENTER": {"icon": "ambulance", "color": "red"}, "PRIVATE CLINIC": {"icon": "star", "color": "purple"}}
    if cluster_markers:
        d = []
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")): continue
            cfg = MAPPING_TYPES.get(str(row.get("prov_type", "")).upper(), {"icon": "info-sign", "color": "blue"})
            d.append([row["loc_latitude"], row["loc_longitude"], cfg["icon"], cfg["color"], row.get("prov_name", ""), get_popup_content(row, radius_km, total_portfolio)])
        FastMarkerCluster(data=d, callback="function(r){var i=L.AwesomeMarkers.icon({icon:r[2],markerColor:r[3],prefix:'fa'});var m=L.marker(new L.LatLng(r[0],r[1]),{icon:i});m.bindTooltip(r[4]);m.bindPopup(r[5]);return m;}", name="Providers").add_to(mapa)
    else:
        l = folium.FeatureGroup(name="Providers").add_to(mapa)
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")): continue
            cfg = MAPPING_TYPES.get(str(row.get("prov_type", "")).upper(), {"icon": "info-sign", "color": "blue"})
            folium.Marker(location=[row["loc_latitude"], row["loc_longitude"]], tooltip=row.get("prov_name"), popup=folium.Popup(get_popup_content(row, radius_km, total_portfolio), max_width=300), icon=folium.Icon(color=cfg["color"], icon=cfg["icon"], prefix='fa')).add_to(l)
    
    if show_radius and radius_km:
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")): continue
            folium.Circle(location=[row["loc_latitude"], row["loc_longitude"]], radius=radius_km * 1000, color="#666", fill=False, weight=1, dash_array="5").add_to(mapa)

def add_heatmap(mapa, df_heat):
    if df_heat.empty: return
    agg = df_heat.dropna(subset=["loc_latitude", "loc_longitude"]).groupby(["loc_latitude", "loc_longitude"]).size().reset_index(name="p")
    HeatMap(agg[["loc_latitude", "loc_longitude", "p"]].values.tolist(), radius=20, blur=15, min_opacity=0.3).add_to(mapa)

def add_ping_marker(mapa, lat, lon, radius_km=None):
    folium.Marker(location=[lat, lon], icon=folium.Icon(color='red', icon='crosshairs', prefix='fa')).add_to(mapa)
    if radius_km: folium.Circle(location=[lat, lon], radius=radius_km*1000, color="red", fill=True, fill_opacity=0.1, weight=1).add_to(mapa)

def add_simulation_marker(mapa, lat, lon, radius_km):
    folium.Marker(location=[lat, lon], icon=folium.Icon(color='green', icon='bullseye', prefix='fa')).add_to(mapa)
    folium.Circle(location=[lat, lon], radius=radius_km*1000, color="#28B463", fill=True, fill_opacity=0.1, weight=2).add_to(mapa)

def apply_layers(m_obj, p_df, m_df, show_h=False, show_m=True, show_r=False, cluster_m=True, rad=0, ping_loc=None, best_pt=None):
    if show_h: add_heatmap(m_obj, m_df)
    if show_m:
        tm = m_df['user_id'].nunique() if 'user_id' in m_df.columns else len(m_df)
        add_provider_markers(m_obj, p_df, radius_km=rad, total_portfolio=tm, show_radius=show_r, cluster_markers=cluster_m)
    if ping_loc: add_ping_marker(m_obj, ping_loc["lat"], ping_loc["lng"], radius_km=rad)
    if best_pt: add_simulation_marker(m_obj, best_pt["lat"], best_pt["lon"], radius_km=rad)

def render_map(mapa, key="main_map"):
    return st_folium(mapa, width=None, use_container_width=True, height=600, returned_objects=["last_clicked"], key=key)
