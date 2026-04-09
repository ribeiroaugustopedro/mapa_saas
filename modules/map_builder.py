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
            if isinstance(value, (list, tuple)): continue
            if pd.notna(value) and str(value).strip().lower() not in ("", "-", "nan"):
                info += f"<b>{label}:</b> {value}<br>"
    if metrics and isinstance(metrics, dict) and radius_km:
        port = metrics.get('portfolio', 0)
        t_port = metrics.get('total_portfolio', total_portfolio if total_portfolio else 0)
        share_port = (port / t_port * 100) if t_port > 0 else 0
        info += (f"<div style='margin-top:8px; border-top: 2px solid #f0f0f0; padding-top: 8px;'><b style='color: #444;'>Within Radius ({radius_km} km):</b><br><table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'><tr><td><b>Portfolio:</b></td><td style='text-align:right'>{port:,} <span style='font-size:10px; color:#666'>/ {t_port:,} ({share_port:.1f}%)</span></td></tr></table></div>")
    elif radius_km:
        col_radius = f"radius_{radius_km}km"
        if col_radius in row and pd.notna(row[col_radius]):
            info += f"<div style='margin-top:6px;'><b>Portfolio ({radius_km} km):</b> {int(row[col_radius]):,}</div>"
    nome = row.get("prov_name", "Provider")
    header_style = "text-align: center; font-weight: bold; font-size: 14px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #ccc; color: #2c3e50;"
    content_html = f"<div style='{header_style}'>{nome}</div><div style='font-size:13px; line-height: 1.4;'>{info}</div>" if info.strip() else f"<div style='{header_style}'>{nome}</div><div style='text-align: center; font-size:13px; color: #7f8c8d;'><i>Information unavailable</i></div>"
    return f"<div class='popup-hosp' style='font-family: Arial, sans-serif;'>{content_html}</div>"

def create_base_map(lat_center, lon_center, map_type="OpenStreetMap", zoom_start=10.5, locked=False):
    options = {"zoomControl": False, "scrollWheelZoom": False, "dragging": False, "doubleClickZoom": False, "boxZoom": False, "touchZoom": False, "keyboard": False} if locked else {}
    m = folium.Map(location=[lat_center, lon_center], zoom_start=zoom_start, tiles=map_type, prefer_canvas=True, **options)
    if not locked:
        Fullscreen().add_to(m); LocateControl().add_to(m); Geocoder().add_to(m); MiniMap().add_to(m); MousePosition().add_to(m)
        MeasureControl(primary_length_unit="kilometers").add_to(m); Draw().add_to(m)
        m.get_root().html.add_child(folium.Element("""<script>function setupOrdering(map){map.on('popupopen',function(e){var m=e.popup._source;if(m){if(m.setZIndexOffset)m.setZIndexOffset(10000);if(m._icon)m._icon.style.zIndex=10000;}});map.on('popupclose',function(e){var m=e.popup._source;if(m){if(m.setZIndexOffset)m.setZIndexOffset(0);if(m._icon)m._icon.style.zIndex="";}});}function applyAll(){var ms=document.getElementsByClassName('folium-map');for(var i=0;i<ms.length;i++){var o=window[ms[i].id];if(o&&!o._p){setupOrdering(o);o._p=true;}}}setInterval(applyAll,1000);</script>"""))
    return m

def add_provider_markers(mapa, df_providers, radius_km=None, total_portfolio=None, show_radius=False, cluster_markers=True):
    if df_providers.empty: return
    MAPPING_TYPES = {"GENERAL HOSPITAL": {"icon": "building", "color": "blue"}, "WOMENS AND CHILDRENS HOSPITAL": {"icon": "heart", "color": "pink"}, "SPECIALTY MEDICAL CENTER": {"icon": "plus-square", "color": "orange"}, "EMERGENCY CENTER": {"icon": "ambulance", "color": "red"}, "PRIVATE CLINIC": {"icon": "star", "color": "darkpurple"}}
    PRIORITY = ["PRIVATE CLINIC", "EMERGENCY CENTER", "WOMENS AND CHILDRENS HOSPITAL", "GENERAL HOSPITAL", "SPECIALTY MEDICAL CENTER"]
    if cluster_markers:
        d = []
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")) or pd.isna(row.get("loc_longitude")): continue
            s = str(row.get("prov_tax_id", "")).upper()
            ia = s in ["P", "A", "ACTIVE", "CREDENTIALED"]
            if "prov_tax_id" in row and not ia: col, ic = "lightgray", "ban"
            else:
                vt = "PRIVATE CLINIC"
                for p in PRIORITY:
                    if p in str(row.get("prov_type", "")).upper(): vt = p; break
                cfg = MAPPING_TYPES.get(vt, {"icon": "info-sign", "color": "blue"})
                col, ic = cfg["color"], cfg["icon"]
            m = row.get("beneficiarios_no_raio_dinamico")
            d.append([row["loc_latitude"], row["loc_longitude"], ic, col, row.get("prov_name", ""), get_popup_content(row, radius_km, total_portfolio, m if isinstance(m, dict) else None)])
        FastMarkerCluster(data=d, callback="function(r){var i=L.AwesomeMarkers.icon({icon:r[2],markerColor:r[3],prefix:'fa'});var m=L.marker(new L.LatLng(r[0],r[1]),{icon:i});m.bindTooltip(r[4]);m.bindPopup(r[5]);return m;}", name="Providers").add_to(mapa)
    else:
        l = folium.FeatureGroup(name="Providers").add_to(mapa)
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")) or pd.isna(row.get("loc_longitude")): continue
            vt = "PRIVATE CLINIC"
            for p in PRIORITY:
                if p in str(row.get("prov_type", "")).upper(): vt = p; break
            cfg = MAPPING_TYPES.get(vt, {"icon": "info-sign", "color": "blue"})
            m = row.get("beneficiarios_no_raio_dinamico")
            folium.Marker(location=[row["loc_latitude"], row["loc_longitude"]], tooltip=row.get("prov_name"), popup=folium.Popup(get_popup_content(row, radius_km, total_portfolio, m if isinstance(m, dict) else None), max_width=320), icon=folium.Icon(color=cfg["color"], icon=cfg["icon"], prefix='fa')).add_to(l)
    if show_radius and radius_km:
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")): continue
            folium.Circle(location=[row["loc_latitude"], row["loc_longitude"]], radius=radius_km * 1000, color="#666", fill=False, weight=1, dash_array="5").add_to(mapa)

def add_heatmap(mapa, df_heat, radius=None, blur=None, count_unique=True):
    if df_heat.empty: return
    df = df_heat.copy()
    if "loc_latitude" in df.columns:
        df["lat_round"] = pd.to_numeric(df["loc_latitude"], errors="coerce").round(5)
        df["lon_round"] = pd.to_numeric(df["loc_longitude"], errors="coerce").round(5)
        df = df.dropna(subset=["lat_round", "lon_round"])
        if "user_id" in df.columns and count_unique: agg = df.groupby(["lat_round", "lon_round"])["user_id"].nunique().reset_index(name="peso")
        else: agg = df.groupby(["lat_round", "lon_round"]).size().reset_index(name="peso")
        if not agg.empty:
            HeatMap(agg[["lat_round", "lon_round", "peso"]].astype(float).values.tolist(), radius=radius if radius else 20, blur=blur if blur else 10, min_opacity=0.25, max_zoom=12, gradient={0.05:'#0000FF',0.25:'#00FF00',0.55:'#FFD700',0.85:'#FF0000',1.0:'#800000'}).add_to(mapa)

def add_ping_marker(mapa, lat, lon, info=None, radius_km=None, metrics=None, address_info=None):
    c = f"<div style='font-weight:bold; margin-bottom:6px;'>Point</div>{info if info else ''}"
    if address_info:
        items = [f"<b>{k}:</b> {v}" for k, v in address_info.items()]
        c += f"<div style='margin-top:8px; background:#f9f9f9; padding:6px; border-radius:4px;'>{'<br>'.join(items)}</div>"
    if metrics and radius_km:
        p, tp = metrics.get('portfolio', 0), metrics.get('total_portfolio', 0)
        c += f"<div style='margin-top:8px; border-top:1px solid #ddd; padding-top:8px;'>Portfolio: {p:,} / {tp:,}</div>"
    folium.Marker(location=[lat, lon], popup=folium.Popup(f"<div style='min-width:240px'>{c}</div>", max_width=320), icon=folium.Icon(color='red')).add_to(mapa)
    if radius_km: folium.Circle(location=[lat, lon], radius=radius_km*1000, color="red", fill=True, fill_opacity=0.1, weight=1, dash_array="5,5").add_to(mapa)

def add_simulation_marker(mapa, lat, lon, count, radius_km, best_e=None, metrics=None, address_info=None):
    i = f"<b>Suggested Location</b><br>Coord: {lat:.4f}, {lon:.4f}"
    if address_info: i += f"<br>{'<br>'.join([f'<b>{k}:</b> {v}' for k, v in address_info.items()])}"
    i += f"<div style='margin-top:8px; background:#EAFAF1; padding:6px; border:1px solid #28B463;'><b>Portfolio ({radius_km} km):</b><br>{count:,}</div>"
    if best_e:
        d = count - best_e[2]
        i += f"<div style='margin-top:8px; color:{'#2ECC71' if d>0 else '#E74C3C'}'>Benchmark: {best_e[3]}<br>{d:+,} vs best</div>"
    folium.Marker(location=[lat, lon], popup=folium.Popup(f"<div style='min-width:240px'>{i}</div>", max_width=320), icon=folium.Icon(color='green', icon='plus', prefix='fa')).add_to(mapa)
    folium.Circle(location=[lat, lon], radius=radius_km*1000, color="#28B463", fill=True, weight=2, dash_array="10,8").add_to(mapa)

def render_map(mapa, key="main_map"):
    LayerControl().add_to(mapa)
    return st_folium(mapa, width=1400, height=700, returned_objects=["last_clicked", "zoom", "center"], key=key)
