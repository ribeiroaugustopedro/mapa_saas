import folium
import pandas as pd
from folium import FeatureGroup, LayerControl
from folium.plugins import (
    Draw, Fullscreen, Geocoder, HeatMap, LocateControl, 
    MiniMap, MeasureControl, MousePosition, MarkerCluster
)
from streamlit_folium import st_folium
from folium.features import DivIcon

def criar_popup_html(row, raio_km=None, total_cart=None, metrics=None):
    info = ""
    campos = [
        ("Status", "ie_prestador"),
        ("CNPJ", "cnpj"),
        ("Tipo de Prestador", "tipo_prestador"),
        ("Classificação Produto", "classificacao_produto"),
        ("Região Agrupada", "regiao_agrupada"),
        ("Região", "regiao"),
        ("Município", "municipio"),
        ("Bairro", "bairro"),
    ]

    for label, col in campos:
        if col in row:
            valor = row[col]
            if isinstance(valor, (list, tuple)):
                continue
            if pd.notna(valor) and str(valor).strip().lower() not in ("", "-", "nan"):
                info += f"<b>{label}:</b> {valor}<br>"

    if metrics and isinstance(metrics, dict) and raio_km:
        cart = metrics.get('carteira', 0)
        t_cart = metrics.get('total_carteira', total_cart if total_cart else 0)
        share_cart = (cart / t_cart * 100) if t_cart > 0 else 0

        info += (
            f"<div style='margin-top:8px; border-top: 2px solid #f0f0f0; padding-top: 8px;'>"
            f"<b style='color: #444;'>No Raio ({raio_km} km):</b><br>"
            f"<table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'>"
            f"<tr><td><b>Carteira:</b></td><td style='text-align:right'>{cart:,} <span style='font-size:10px; color:#666'>/ {t_cart:,} ({share_cart:.1f}%)</span></td></tr>"
            f"</table>"
            f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share sobre total geral</div>"
            f"</div>"
        )
    
    elif raio_km:
        col_raio = f"raio_{raio_km}km"
        if col_raio in row and pd.notna(row[col_raio]):
            n_raio = int(row[col_raio])
            info += (
                f"<div style='margin-top:6px;'>"
                f"<b>Carteira ({raio_km} km):</b> {n_raio:,}"
                f"</div>"
            )

    nome = row.get("nome_prestador", "Prestador")
    
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
            f"<i>Informações indisponíveis</i>"
            f"</div>"
        )

    return folium.Popup(
        f"<div class='popup-hosp' style='font-family: Arial, sans-serif;'>{content_html}</div>",
        max_width=320
    )

def criar_mapa_base(lat_centro, lon_centro, tipo_mapa="OpenStreetMap", zoom_start=10.5, travado=False):
    options = {}
    if travado:
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
        location=[lat_centro, lon_centro], 
        zoom_start=zoom_start, 
        tiles=tipo_mapa, 
        prefer_canvas=True,
        **options
    )
    
    if not travado:
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

def adicionar_marcadores_prestadores(mapa, df_prestadores, raio_km=None, total_cart=None, mostrar_raio=False, agrupar_marcadores=True):
    if agrupar_marcadores:
        camada = MarkerCluster(name="Prestadores").add_to(mapa)
    else:
        camada = folium.FeatureGroup(name="Prestadores").add_to(mapa)
    
    if df_prestadores.empty:
        return

    MAPPING_TYPES = {
        "HOSPITAL GERAL": {"icon": "building", "color": "blue"},
        "MATERNIDADE": {"icon": "heart", "color": "pink"}, 
        "HOSPITAL ESPECIALIZADO": {"icon": "plus-square", "color": "orange"},
        "PRONTO SOCORRO": {"icon": "ambulance", "color": "red"},
        "LEVE CLINICA": {"icon": "star", "color": "darkpurple"}
    }
    
    PRIORITY_ORDER = [
        "LEVE CLINICA",
        "PRONTO SOCORRO",
        "MATERNIDADE",
        "HOSPITAL GERAL", 
        "HOSPITAL ESPECIALIZADO"
    ]

    for _, row in df_prestadores.iterrows():
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
            continue

        raw_tipo = str(row.get("tipo_prestador", "")).strip().upper()
        tipos_set = set(t.strip() for t in raw_tipo.split("|") if t.strip())
        
        status = str(row.get("ie_prestador", "")).strip().upper()
        
        is_ativo = status in ["P", "A", "ATIVO", "CREDENCIADO"]
        
        if "ie_prestador" in row and not is_ativo:
            cor_marcador = "lightgray"
            icone = "ban"
        else:
            tipo_visual = "CLÍNICA"
            found = False
            
            for p_type in PRIORITY_ORDER:
                if p_type in tipos_set:
                    tipo_visual = p_type
                    found = True
                    break
            
            if not found:
                for t in tipos_set:
                    if t in MAPPING_TYPES:
                        tipo_visual = t
                        break
            
            config = MAPPING_TYPES.get(tipo_visual, {"icon": "info-sign", "color": "blue"})
            cor_marcador = config["color"]
            icone = config["icon"]

        metrics = row.get("beneficiarios_no_raio_dinamico", None)
        if hasattr(metrics, 'get') is False: metrics = None
        popup = criar_popup_html(row, raio_km, total_cart, metrics=metrics)

        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            tooltip=row.get("nome_prestador", "Prestador"),
            popup=popup,
            icon=folium.Icon(color=cor_marcador, icon=icone, prefix='fa'),
            rise_on_hover=True
        ).add_to(camada)

        if mostrar_raio and raio_km:
            CSS_COLORS = {
                "darkpurple": "#5d1a60",
                "pink": "#FF1493",
                "lightgray": "#808080",
                "blue": "#3388ff",
                "green": "green",
                "red": "red",
                "orange": "orange",
            }
            cor_circulo = CSS_COLORS.get(cor_marcador, cor_marcador)

            folium.Circle(
                location=[row["latitude"], row["longitude"]],
                radius=raio_km * 1000,
                color=cor_circulo,
                fill=False,
                weight=1,
                dash_array="5"
            ).add_to(mapa)

def adicionar_heatmap(mapa, df_heat, bounds=None, zoom_level=None, radius=None, blur=None, gradient=None, count_unique=True):
    if df_heat.empty:
        return

    df_processing = df_heat.copy()
    if "latitude" in df_processing.columns and "longitude" in df_processing.columns:
        df_processing["lat_round"] = pd.to_numeric(df_processing["latitude"], errors="coerce").round(5)
        df_processing["lon_round"] = pd.to_numeric(df_processing["longitude"], errors="coerce").round(5)
        
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
        
        if "id_usuario" in df_processing.columns and count_unique:
            agg = (
                df_processing.groupby(["lat_round", "lon_round"])
                .agg({"id_usuario": "nunique"})
                .reset_index()
                .rename(columns={"lat_round": "latitude", "lon_round": "longitude", "id_usuario": "peso"})
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
            final_blur = blur if blur is not None else 20
            
            if radius is None and blur is None and zoom_level is not None:
                if zoom_level >= 13:
                    final_radius, final_blur = 15, 15
                elif zoom_level >= 11:
                    final_radius, final_blur = 18, 18
                elif zoom_level <= 8:
                    final_radius, final_blur = 25, 25
            
            HeatMap(
                agg[["latitude", "longitude", "peso"]].astype(float).values.tolist(),
                radius=final_radius,
                blur=final_blur,
                min_opacity=0.3,
                max_zoom=18,
                gradient=gradient
            ).add_to(mapa)

def adicionar_marcador_ping(mapa, lat, lon, info=None, raio_km=None, metrics=None, address_info=None):
    popup_obj = criar_popup_html({"nome_prestador": "Ponto selecionado"}, raio_km=raio_km, metrics=metrics)
    
    if info or address_info:
        nome = "Ponto selecionado"
        content = f"<div style='font-weight:bold; margin-bottom:6px;'>{nome}</div>"
        
        if info:
            content += info

        if address_info and isinstance(address_info, dict):
            items = []
            order = ['CEP', 'Região Agrupada', 'Região', 'Município', 'Bairro']
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

        if metrics and isinstance(metrics, dict) and raio_km:
            cart = metrics.get('carteira', 0)
            t_cart = metrics.get('total_carteira', 0)
            share_cart = (cart / t_cart * 100) if t_cart > 0 else 0

            content += (
                f"<div style='margin-top:8px; border-top: 2px solid #f0f0f0; padding-top: 8px;'>"
                f"<b style='color: #444;'>No Raio ({raio_km} km):</b><br>"
                f"<table style='width:100%; border-collapse: collapse; margin-top:4px; font-size:12px;'>"
                f"<tr><td><b>Carteira:</b></td><td style='text-align:right'>{cart:,} <span style='font-size:10px; color:#666'>/ {t_cart:,} ({share_cart:.1f}%)</span></td></tr>"
                f"</table>"
                f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share sobre total geral</div>"
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
        tooltip="Ponto Selecionado",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(mapa)
    
    if raio_km:
         folium.Circle(
            location=[lat, lon],
            radius=raio_km * 1000,
            color="red",
            fill=True,
            fill_opacity=0.1,
            weight=1,
            dash_array="5, 5"
        ).add_to(mapa)

def adicionar_marcador_simulacao(mapa, lat, lon, count, raio_km, melhor_e=None, metric_name="Carteira", metrics=None, address_info=None):
    style_comp = ""
    info_comp = ""
    
    if melhor_e:
        lat_e, lon_e, count_e, nome_e = melhor_e
        diff = count - count_e
        perc = (count / count_e - 1) * 100 if count_e > 0 else 0
        
        if diff > 0:
            color_text = "#2ECC71"
            txt = f"Superior ao melhor atual (+{diff:,} / {perc:+.1f}%)"
        elif diff < 0:
            color_text = "#E74C3C"
            txt = f"Inferior ao melhor atual ({diff:,} / {perc:.1f}%)"
        else:
            color_text = "#95A5A6"
            txt = "Captação idêntica ao melhor atual"
            
        info_comp = (
            f"<div style='margin-top:8px; border-top: 1px solid #ddd; padding-top: 8px; font-size: 12px; color: {color_text};'>"
            f"<b>Benchmark:</b> {nome_e}<br>{txt}"
            f"</div>"
        )

    info_metrics = ""
    if metrics and isinstance(metrics, dict):
        cart = metrics.get('carteira', 0)
        t_cart = metrics.get('total_carteira', 0)
        share_cart = (cart / t_cart * 100) if t_cart > 0 else 0

        info_metrics = (
            f"<div style='margin-top:8px; border-top: 1px solid #ddd; padding-top: 8px;'>"
            f"<table style='width:100%; border-collapse: collapse; font-size:12px;'>"
            f"<tr><td><b>Carteira:</b></td><td style='text-align:right'>{cart:,} <span style='font-size:10px; color:#666'>/ {t_cart:,} ({share_cart:.1f}%)</span></td></tr>"
            f"</table>"
            f"<div style='font_size:9px; color:#999; margin-top:4px; text-align:right'>*Share sobre total geral</div>"
            f"</div>"
        )

    info_address = ""
    if address_info and isinstance(address_info, dict):
        items = []
        order = ['CEP', 'Região Agrupada', 'Região', 'Município', 'Bairro']
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
        f"<b style='color: #28B463; font-size: 16px;'>Ponto sugerido</b><br>"
        f"<div style='margin-top:4px;'>Coord: {lat:.4f}, {lon:.4f}</div>"
        f"{info_address}"
        f"<div style='margin-top:8px; background: #EAFAF1; padding: 6px; border-radius: 4px; border: 1px solid #28B463;'>"
        f"<b>Métrica principal ({raio_km} km):</b><br>"
        f"<span style='font-size: 18px; font-weight: bold;'>{count:,}</span> {metric_name}"
        f"</div>"
        f"{info_metrics}"
        f"{info_comp}"
        f"</div>"
    )
    
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(f"<div style='min-width: 240px'>{info}</div>", max_width=320, show=True),
        tooltip="Sugerir Nova Localização",
        icon=folium.Icon(color='green', icon='plus', prefix='fa')
    ).add_to(mapa)
    
    folium.Circle(
        location=[lat, lon],
        radius=raio_km * 1000,
        color="#28B463",
        fill=True,
        fill_opacity=0.1,
        weight=2,
        dash_array="10, 8"
    ).add_to(mapa)

def renderizar_mapa(mapa):
    LayerControl().add_to(mapa)
    return st_folium(
        mapa, 
        width=1200, 
        height=600,
        returned_objects=["last_clicked", "zoom", "center"]
    )
