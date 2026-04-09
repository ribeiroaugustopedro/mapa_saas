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
    fields = [
        ("Status", "prov_tax_id"),
        ("Type", "prov_type"),
        ("Region", "loc_region"),
        ("City", "loc_city"),
        ("Neighborhood", "loc_neighborhood"),
        ("ZIP Code", "loc_zip_code"),
    ]

    for label, col in fields:
        if col in row:
            value = row[col]
            if isinstance(value, (list, tuple)):
                continue
            if pd.notna(value) and str(value).strip().lower() not in ("", "-", "nan"):
                info += f"<b>{label}:</b> {value}<br>"

    if metrics and isinstance(metrics, dict) and radius_km:
        port = metrics.get('portfolio', 0)
        t_port = metrics.get('total_portfolio', total_portfolio if total_portfolio else 0)
        share_port = (port / t_port * 100) if t_port > 0 else 0

        info += (
            f"<div style='margin-top:8px; border-top: 2px solid #f0f0f0; padding-top: 8px;'>"
            f"<b style='color: #444;'>Within Radius ({radius_km} km):</b><br>"
            f"<table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'>"
            f"<tr><td><b>Portfolio:</b></td><td style='text-align:right'>{port:,} <span style='font-size:10px; color:#666'>/ {t_port:,} ({share_port:.1f}%)</span></td></tr>"
            f"</table>"
            f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share over total population</div>"
            f"</div>"
        )
    
    elif radius_km:
        col_radius = f"radius_{radius_km}km"
        if col_radius in row and pd.notna(row[col_radius]):
            n_radius = int(row[col_radius])
            info += (
                f"<div style='margin-top:6px;'>"
                f"<b>Portfolio ({radius_km} km):</b> {n_radius:,}"
                f"</div>"
            )

    nome = row.get("prov_name", "Provider")
    
    header_style = (
        "text-align: center; "
        "font-weight: bold; "
        "font-size: 14px; "
        "margin-bottom: 8px; "
        "padding-bottom: 8px; "
        "border-bottom: 1px solid #ccc; "
        "color: #2c3e50;"
    )
    
    content_html = ""
    if info.strip():
        content_html = f"<div style='{header_style}'>{nome}</div><div style='font-size:13px; line-height: 1.4;'>{info}</div>"
    else:
        content_html = (
            f"<div style='{header_style}'>{nome}</div>"
            f"<div style='text-align: center; font-size:13px; color: #7f8c8d;'>"
            f"<i>Information unavailable</i>"
            f"</div>"
        )

    return f"<div class='popup-hosp' style='font-family: Arial, sans-serif;'>{content_html}</div>"

def create_popup_html(row, radius_km=None, total_portfolio=None, metrics=None):
    html = get_popup_content(row, radius_km, total_portfolio, metrics)
    return folium.Popup(html, max_width=320)

def create_base_map(lat_center, lon_center, map_type="OpenStreetMap", zoom_start=10.5, locked=False):
    options = {}
    if locked:
        options = {
            "zoomControl": False,
            "scrollWheelZoom": False,
            "dragging": False,
            "doubleClickZoom": False,
            "boxZoom": False,
            "touchZoom": False,
            "keyboard": False
        }
        
    m = folium.Map(
        location=[lat_center, lon_center], 
        zoom_start=zoom_start, 
        tiles=map_type, 
        prefer_canvas=True, # Canvas helps performance with many markers
        **options
    )
    
    if not locked:
        Fullscreen().add_to(m)
        LocateControl().add_to(m)
        Geocoder().add_to(m)
        MiniMap().add_to(m)
        MousePosition().add_to(m)
        MeasureControl(primary_length_unit="kilometers").add_to(m)
        Draw().add_to(m)

        script = """
        <script>
        function setupMarkerOrdering(map) {
            map.on('popupopen', function(e) {
                var marker = e.popup._source;
                if (marker) {
                    if (marker.setZIndexOffset) marker.setZIndexOffset(10000);
                    if (marker._icon) marker._icon.style.zIndex = 10000;
                }
            });
            map.on('popupclose', function(e) {
                var marker = e.popup._source;
                if (marker) {
                    if (marker.setZIndexOffset) marker.setZIndexOffset(0);
                    if (marker._icon) marker._icon.style.zIndex = "";
                }
            });
        }
        
        function applyToAllMaps() {
            var maps = document.getElementsByClassName('folium-map');
            for (var i = 0; i < maps.length; i++) {
                var mapId = maps[i].id;
                var mapObj = window[mapId];
                if (mapObj && !mapObj._priority_setup) {
                    setupMarkerOrdering(mapObj);
                    mapObj._priority_setup = true;
                }
            }
        }

        var checkMap = setInterval(applyToAllMaps, 1000);
        setTimeout(applyToAllMaps, 500);
        </script>
        """
        m.get_root().html.add_child(folium.Element(script))
    
    return m

def add_provider_markers(mapa, df_providers, radius_km=None, total_portfolio=None, show_radius=False, cluster_markers=True):
    if df_providers.empty:
        return

    MAPPING_TYPES = {
        "GENERAL HOSPITAL": {"icon": "building", "color": "blue"},
        "WOMENS AND CHILDRENS HOSPITAL": {"icon": "heart", "color": "pink"}, 
        "SPECIALTY MEDICAL CENTER": {"icon": "plus-square", "color": "orange"},
        "EMERGENCY CENTER": {"icon": "ambulance", "color": "red"},
        "PRIVATE CLINIC": {"icon": "star", "color": "darkpurple"}
    }
    
    PRIORITY_ORDER = [
        "PRIVATE CLINIC",
        "EMERGENCY CENTER",
        "WOMENS AND CHILDRENS HOSPITAL",
        "GENERAL HOSPITAL", 
        "SPECIALTY MEDICAL CENTER"
    ]

    callback = """
        function (row) {
            var icon = L.AwesomeMarkers.icon({
                icon: row[2],
                markerColor: row[3],
                prefix: 'fa'
            });
            var marker = L.marker(new L.LatLng(row[0], row[1]), {icon: icon});
            marker.bindTooltip(row[4]);
            marker.bindPopup(row[5]);
            return marker;
        };
    """

    if cluster_markers:
        marker_data = []
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")) or pd.isna(row.get("loc_longitude")): continue
            
            raw_type = str(row.get("prov_type", "")).strip().upper()
            status = str(row.get("prov_tax_id", "")).strip().upper()
            is_active = status in ["P", "A", "ACTIVE", "CREDENTIALED"]
            
            if "prov_tax_id" in row and not is_active:
                marker_color, icon = "lightgray", "ban"
            else:
                visual_type = "PRIVATE CLINIC"
                for p_type in PRIORITY_ORDER:
                    if p_type in raw_type:
                        visual_type = p_type
                        break
                config = MAPPING_TYPES.get(visual_type, {"icon": "info-sign", "color": "blue"})
                marker_color, icon = config["color"], config["icon"]

            metrics = row.get("beneficiarios_no_raio_dinamico", None)
            if hasattr(metrics, 'get') is False: metrics = None
            popup_html = get_popup_content(row, radius_km, total_portfolio, metrics=metrics)
            
            marker_data.append([
                row["loc_latitude"], 
                row["loc_longitude"], 
                icon, 
                marker_color, 
                row.get("prov_name", "Provider"),
                popup_html
            ])
        
        FastMarkerCluster(data=marker_data, callback=callback, name="Providers").add_to(mapa)
    else:
        layer = folium.FeatureGroup(name="Providers").add_to(mapa)
        for _, row in df_providers.iterrows():
            if pd.isna(row.get("loc_latitude")) or pd.isna(row.get("loc_longitude")): continue
            
            status = str(row.get("prov_tax_id", "")).strip().upper()
            is_active = status in ["P", "A", "ACTIVE", "CREDENTIALED"]
            if "prov_tax_id" in row and not is_active:
                marker_color, icon = "lightgray", "ban"
            else:
                visual_type = "PRIVATE CLINIC"
                for p_type in PRIORITY_ORDER:
                    if p_type in str(row.get("prov_type", "")).upper():
                        visual_type = p_type
                        break
                config = MAPPING_TYPES.get(visual_type, {"icon": "info-sign", "color": "blue"})
                marker_color, icon = config["color"], config["icon"]

            metrics = row.get("beneficiarios_no_raio_dinamico", None)
            if hasattr(metrics, 'get') is False: metrics = None
            popup = create_popup_html(row, radius_km, total_portfolio, metrics=metrics)

            folium.Marker(
                location=[row["loc_latitude"], row["loc_longitude"]],
                tooltip=row.get("prov_name", "Provider"),
                popup=popup,
                icon=folium.Icon(color=marker_color, icon=icon, prefix='fa'),
                rise_on_hover=True
            ).add_to(layer)

    if show_radius and radius_km:
        for _, row in df_providers.iterrows():
             if pd.isna(row.get("loc_latitude")) or pd.isna(row.get("loc_longitude")): continue
             folium.Circle(
                location=[row["loc_latitude"], row["loc_longitude"]],
                radius=radius_km * 1000,
                color="#666",
                fill=False,
                weight=1,
                dash_array="5"
            ).add_to(mapa)

def add_heatmap(mapa, df_heat, bounds=None, zoom_level=None, radius=None, blur=None, gradient=None, count_unique=True):
    if df_heat.empty:
        return

    df_processing = df_heat.copy()
    if "loc_latitude" in df_processing.columns and "loc_longitude" in df_processing.columns:
        df_processing["lat_round"] = pd.to_numeric(df_processing["loc_latitude"], errors="coerce").round(5)
        df_processing["lon_round"] = pd.to_numeric(df_processing["loc_longitude"], errors="coerce").round(5)
        
        df_processing = df_processing.dropna(subset=["lat_round", "lon_round"])
        
        if bounds is not None:
            lat_min, lat_max = bounds.get("lat_min"), bounds.get("lat_max")
            lon_min, lon_max = bounds.get("lon_min"), bounds.get("lon_max")
            
            if all([lat_min, lat_max, lon_min, lon_max]):
                mask = (
                    (df_processing["lat_round"] >= lat_min) &
                    (df_processing["lat_round"] <= lat_max) &
                    (df_processing["lon_round"] >= lon_min) &
                    (df_processing["lon_round"] <= lon_max)
                )
                df_processing = df_processing[mask]
        
        if "user_id" in df_processing.columns and count_unique:
            agg = (
                df_processing.groupby(["lat_round", "lon_round"])
                .agg({"user_id": "nunique"})
                .reset_index()
                .rename(columns={"lat_round": "latitude", "lon_round": "longitude", "user_id": "peso"})
            )
        else:
            if "qtd" in df_processing.columns:
                agg = (
                    df_processing.groupby(["lat_round", "lon_round"])
                    .agg({"qtd": "sum"})
                    .reset_index()
                    .rename(columns={"lat_round": "latitude", "lon_round": "longitude", "qtd": "peso"})
                )
            else:
                agg = (
                    df_processing.groupby(["lat_round", "lon_round"])
                    .size()
                    .reset_index(name="peso")
                    .rename(columns={"lat_round": "latitude", "lon_round": "longitude"})
                )

        if not agg.empty:
            final_radius = radius if radius is not None else 20
            final_blur = blur if blur is not None else 10
            
            if radius is None and blur is None and zoom_level is not None:
                if zoom_level >= 13:
                    final_radius, final_blur = 10, 10
                elif zoom_level >= 11:
                    final_radius, final_blur = 12, 12
                elif zoom_level <= 8:
                    final_radius, final_blur = 15, 10
                elif zoom_level <= 6:
                    final_radius, final_blur = 18, 12
                elif zoom_level <= 4:
                    final_radius, final_blur = 20, 15
            
            HeatMap(
                agg[["latitude", "longitude", "peso"]].astype(float).values.tolist(),
                radius=final_radius,
                blur=final_blur,
                min_opacity=0.25,
                max_zoom=12,
                gradient={
                    0.05: '#0000FF', # Deep Blue
                    0.15: '#00FFFF', # Cyan
                    0.25: '#00FF00', # Green
                    0.35: '#ADFF2F', # GreenYellow
                    0.45: '#FFFF00', # Yellow
                    0.55: '#FFD700', # Gold
                    0.65: '#FFA500', # Orange
                    0.75: '#FF4500', # OrangeRed
                    0.85: '#FF0000', # Red
                    0.95: '#B22222', # FireBrick
                    1.0: '#800000'    # Maroon
                }
            ).add_to(mapa)

def add_ping_marker(mapa, lat, lon, info=None, radius_km=None, metrics=None, address_info=None):
    popup_obj = create_popup_html({"prov_name": "Selected Point"}, radius_km=radius_km, metrics=metrics)
    
    if info or address_info:
        nome = "Selected Point"
        content = f"<div style='font-weight:bold; margin-bottom:6px;'>{nome}</div>"
        
        if info:
            content += info

        if address_info and isinstance(address_info, dict):
            items = []
            order = ['ZIP Code', 'Region', 'City', 'Neighborhood']
            for k in order:
                if k in address_info:
                    items.append(f"<b>{k}:</b> {address_info[k]}")
            
            for k, v in address_info.items():
                if k not in order:
                    items.append(f"<b>{k}:</b> {v}")
                    
            if items:
                content += (
                    f"<div style='margin-top:8px; background: #f9f9f9; padding: 6px; border-radius: 4px; font-size: 12px; color: #555;'>"
                    f"{'<br>'.join(items)}"
                    f"</div>"
                )

        if metrics and isinstance(metrics, dict) and radius_km:
            port = metrics.get('portfolio', 0)
            t_port = metrics.get('total_portfolio', 0)
            share_port = (port / t_port * 100) if t_port > 0 else 0

            content += (
                f"<div style='margin-top:8px; border-top: 2px solid #f0f0f0; padding-top: 8px;'>"
                f"<b style='color: #444;'>Within Radius ({radius_km} km):</b><br>"
                f"<table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'>"
                f"<tr><td><b>Portfolio:</b></td><td style='text-align:right'>{port:,} <span style='font-size:10px; color:#666'>/ {t_port:,} ({share_port:.1f}%)</span></td></tr>"
                f"</table>"
                f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share over total population</div>"
                f"</div>"
            )
        
        popup_obj = folium.Popup(
            f"<div class='popup-hosp' style='font-size:14px; min-width: 240px;'>{content}</div>",
            max_width=320,
            show=True
        )

    folium.Marker(
        location=[lat, lon],
        popup=popup_obj,
        tooltip="Selected Point",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(mapa)
    
    if radius_km:
         folium.Circle(
            location=[lat, lon],
            radius=radius_km * 1000,
            color="red",
            fill=True,
            fill_opacity=0.1,
            weight=1,
            dash_array="5, 5"
        ).add_to(mapa)

def add_simulation_marker(mapa, lat, lon, count, radius_km, best_e=None, metric_name="Portfolio", metrics=None, address_info=None):
    style_comp = ""
    info_comp = ""
    
    if best_e:
        lat_e, lon_e, count_e, name_e = best_e
        diff = count - count_e
        perc = (count / count_e - 1) * 100 if count_e > 0 else 0
        
        if diff > 0:
            color_text = "#2ECC71"
            txt = f"Superior to best current (+{diff:,} / {perc:+.1f}%)"
        elif diff < 0:
            color_text = "#E74C3C"
            txt = f"Inferior to best current ({diff:,} / {perc:.1f}%)"
        else:
            color_text = "#95A5A6"
            txt = "Identical capture to best current"
            
        info_comp = (
            f"<div style='margin-top:8px; border-top: 1px solid #ddd; padding-top: 8px; font-size: 12px; color: {color_text};'>"
            f"<b>Benchmark:</b> {name_e}<br>{txt}"
            f"</div>"
        )

    info_metrics = ""
    if metrics and isinstance(metrics, dict):
        port = metrics.get('portfolio', 0)
        t_port = metrics.get('total_portfolio', 0)
        share_port = (port / t_port * 100) if t_port > 0 else 0

        info_metrics = (
            f"<div style='margin-top:8px; border-top: 1px solid #ddd; padding-top: 8px;'>"
            f"<table style='width:100%; border-collapse: collapse; font-size:12px;'>"
            f"<tr><td><b>Portfolio:</b></td><td style='text-align:right'>{port:,} <span style='font-size:10px; color:#666'>/ {t_port:,} ({share_port:.1f}%)</span></td></tr>"
            f"</table>"
            f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share over total population</div>"
            f"</div>"
        )

    info_address = ""
    if address_info and isinstance(address_info, dict):
        items = []
        order = ['ZIP Code', 'Region', 'City', 'Neighborhood']
        for k in order:
            if k in address_info:
                items.append(f"<b>{k}:</b> {address_info[k]}")
        
        for k, v in address_info.items():
            if k not in order:
                items.append(f"<b>{k}:</b> {v}")
                
        if items:
            info_address = (
                f"<div style='margin-top:8px; background: #f9f9f9; padding: 6px; border-radius: 4px; font-size: 12px; color: #555;'>"
                f"{'<br>'.join(items)}"
                f"</div>"
            )

    info = (
        f"<div style='font-family: Arial, sans-serif;'>"
        f"<b style='color: #28B463; font-size: 16px;'>Suggested Location</b><br>"
        f"<div style='margin-top:4px;'>Coord: {lat:.4f}, {lon:.4f}</div>"
        f"{info_address}"
        f"<div style='margin-top:8px; background: #EAFAF1; padding: 6px; border-radius: 4px; border: 1px solid #28B463;'>"
        f"<b>Main Metric ({radius_km} km):</b><br>"
        f"<span style='font-size: 18px; font-weight: bold;'>{count:,}</span> {metric_name}"
        f"</div>"
        f"{info_metrics}"
        f"{info_comp}"
        f"</div>"
    )
    
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(f"<div style='min-width: 240px'>{info}</div>", max_width=320, show=True),
        tooltip="Suggest New Location",
        icon=folium.Icon(color='green', icon='plus', prefix='fa')
    ).add_to(mapa)
    
    folium.Circle(
        location=[lat, lon],
        radius=radius_km * 1000,
        color="#28B463",
        fill=True,
        fill_opacity=0.1,
        weight=2,
        dash_array="10, 8"
    ).add_to(mapa)

def render_map(mapa, key="main_map"):
    LayerControl().add_to(mapa)
    return st_folium(
        mapa, 
        width=1400, 
        height=700,
        returned_objects=["last_clicked", "zoom", "center"],
        key=key
    )
