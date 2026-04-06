import streamlit as st
import pandas as pd
from pathlib import Path
import datetime
import json
import os

from modules.data import get_data
from modules.utils import (
    gerar_filtros, detectar_colunas_filtro, encontrar_ponto_otimo, 
    salvar_mapa_como_imagem
)
from modules.map_builder import (
    criar_mapa_base, 
    adicionar_marcadores_prestadores, 
    adicionar_heatmap, 
    renderizar_mapa,
    adicionar_marcador_ping,
    adicionar_marcador_simulacao
)
from modules.dashboard import (
    renderizar_dashboard_carteira, 
    renderizar_dashboard_prestadores,
    calcular_contagem_beneficiarios_raio, 
    calcular_metricas_ponto_completas,
    identificar_regiao_proxima
)
from modules.agent_ai import generate_data_summary, ask_agent


st.set_page_config(layout="wide", page_title="Mapa Dinâmico")

css_path = Path(__file__).parent / ".streamlit" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "ping_location" not in st.session_state:
    st.session_state["ping_location"] = None
if "trigger_printscreen" not in st.session_state:
    st.session_state["trigger_printscreen"] = False
if "ultimo_print_info" not in st.session_state:
    st.session_state["ultimo_print_info"] = None

try:
    df_prestadores, df_carteira, df_geo = get_data()
except Exception as e:
    st.error(f"Erro no carregamento de base: {str(e)}")
    df_prestadores, df_carteira, df_geo = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


if df_prestadores.empty:
    st.warning("Dados não carregados. Verifique os arquivos na pasta 'dataset'.")
    st.stop()


tab_filtros, tab_ai = st.sidebar.tabs(["Filtros", "Assistente IA"])

with tab_filtros:
    if st.button("Reset Geral", use_container_width=True, help="Remove todos os filtros e restaura o mapa para a visão original."):
        for key in list(st.session_state.keys()):
            if key.startswith("sidebar_tab_") or key.startswith("expander_carteira_auto_"):
                del st.session_state[key]
                
        reset_keys = [
            "last_map_center", "last_map_zoom", "ping_location", 
            "resultado_simulacao", "benchmark_simulacao", "trigger_simulacao",
            "busca_prestador", "modo_mapa", "raio_km", "tipo_mapa", "modo_travado",
            "ativo_pin_clique", "mostrar_marcadores_prestadores", "agrupar_marcadores"
        ]
        for k in reset_keys:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    with st.expander("Exportacao e Visual", expanded=False):
        tipo_mapa = st.selectbox(
            "Tema do Mapa",
            ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"],
            key="tipo_mapa"
        )
        modo_travado = st.toggle(
            "Bloquear Zoom (Print)",
            value=False,
            key="modo_travado",
            help="Trava o zoom e o movimento do mapa para facilitar prints estáticos."
        )
        if st.button("Restaurar Zoom Inicial", use_container_width=True, help="Recentraliza o mapa inteiro na tela para caber todos os pontos."):
            st.session_state["last_map_center"] = None
            st.session_state["last_map_zoom"] = None
            st.rerun()
            
        if st.button("Capturar Tela", use_container_width=True, type="primary", help="Salva uma imagem do mapa atual e permite o download."):
            st.session_state["trigger_printscreen"] = True
            st.session_state["ultimo_print_info"] = None
            
        if st.session_state.get("ultimo_print_info"):
            print_info = st.session_state["ultimo_print_info"]
            st.success("Visão do mapa capturada!")
            col_dl, col_cl = st.columns([3, 1])
            with col_dl:
                with open(print_info["path"], "rb") as f:
                    st.download_button(
                        label=f"Baixar {print_info['filename']}",
                        data=f,
                        file_name=print_info["filename"],
                        mime="image/png",
                        use_container_width=True,
                        type="primary",
                        key="dl_btn_final"
                    )
            with col_cl:
                if st.button("Limpar", use_container_width=True):
                    st.session_state["ultimo_print_info"] = None
                    st.rerun()
            
    st.markdown("### Analise")
    
    ativo_pin_clique = st.toggle(
        "Pino Manual",
        value=False,
        key="ativo_pin_clique",
        help="Clicar no mapa posiciona um marcador manual. Se desmarcado, o clique não altera o pino."
    )

    if st.session_state["ping_location"]:
        if st.button("Remover Pino", use_container_width=True, help="Remove o marcador manual do mapa."):
            st.session_state["ping_location"] = None
            st.rerun()
    
    modo_mapa = st.multiselect(
        "Visualizacao",
        ["Heatmap (Carteira)", "Raio (Abrangencia)"],
        key="modo_mapa",
        help="Adicione camadas de calor (Heatmaps) ou visualize o raio de abrangência."
    )
    
    raio_km = st.slider("Raio (km)", 0, 20, 0, key="raio_km", help="Defina o raio de abrangência (km) para análise de cobertura ao redor dos prestadores.")
    
    st.markdown("### Simulacao Geografica")
    metrica_sim = st.selectbox(
        "Metrica",
        ["Carteira"],
        index=0,
        key="metrica_sim",
        help="Escolha qual a métrica da simulação de ponto otimizado."
    )
    
    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        if st.button("Atingir meta", use_container_width=True, type="primary", help="Simula a melhor localização para um novo prestador."):
            st.session_state["trigger_simulacao"] = True
    with col_meta2:
        if st.button("Remover meta", use_container_width=True, help="Limpa o resultado da simulação."):
            st.session_state["resultado_simulacao"] = None
            st.session_state["benchmark_simulacao"] = None
            st.session_state["trigger_simulacao"] = False
            st.rerun()

    st.markdown("---")
    st.markdown("### Rede de Prestadores")

    col_pin1, col_pin2 = st.columns(2)
    with col_pin1:
        mostrar_marcadores = st.toggle(
            "Marcadores",
            value=True,
            key="mostrar_marcadores_prestadores",
            help="Exibe ou oculta os ícones dos prestadores no mapa."
        )
    with col_pin2:
        agrupar_marcadores = st.toggle(
            "Agrupamento",
            value=True,
            key="agrupar_marcadores",
            help="Agrupa marcadores muito próximos para não pesar a visão. Desligue para ver os pinos de forma isolada."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    busca_multi = []
    if "nome_prestador" in df_prestadores.columns:
        opcoes_busca = sorted(df_prestadores["nome_prestador"].dropna().astype(str).unique())
            
        busca_multi = st.multiselect(
            "Busca Nominal", 
            options=opcoes_busca, 
            placeholder="Digite os nomes...",
            key="busca_prestador"
        )

    df_prestadores_cat_filtrado = df_prestadores.copy()

    with st.expander("Filtros Avancados", expanded=False):
        cfg_ignore_prestadores = ["id_prestador", "latitude", "longitude", "cep", "cnpj", "nome_prestador", "raio_5km", "raio_10km", "raio_15km", "raio_20km"]

        config_sidebar = detectar_colunas_filtro(df_prestadores, colunas_ignoradas=cfg_ignore_prestadores)
        
        for cfg in config_sidebar:
            if cfg["col"] == "ie_prestador":
                cfg["label"] = "Status Cadastral"

        df_prestadores_cat_filtrado = gerar_filtros(
            df_prestadores_cat_filtrado,
            st,
            config_sidebar,
            key_prefix="sidebar_tab"
        )

    if busca_multi:
        df_prestadores_nome_filtrado = df_prestadores[
            df_prestadores["nome_prestador"].isin(busca_multi)
        ]
        
        active_cat_filters = False
        cat_cols = [c['col'] for c in config_sidebar]
        for col in cat_cols:
            key = f"sidebar_tab_{col}"
            if key in st.session_state and st.session_state[key]:
                active_cat_filters = True
                break
        
        if active_cat_filters:
            df_prestadores_filtrado = pd.concat([df_prestadores_cat_filtrado, df_prestadores_nome_filtrado]).drop_duplicates(subset=["id_prestador"])
        else:
            df_prestadores_filtrado = df_prestadores_nome_filtrado
    else:
        df_prestadores_filtrado = df_prestadores_cat_filtrado

    st.markdown("---")
    st.markdown("### Filtros da Base de Clientes")

    with st.expander("Filtros Cadastrais (Carteira)", expanded=False):
        IGNORE_CARTEIRA = ["id_usuario", "cep", "latitude", "longitude"]
        config_carteira = detectar_colunas_filtro(df_carteira, colunas_ignoradas=IGNORE_CARTEIRA)
        config_carteira.sort(key=lambda x: x["label"])

        df_carteira_filtrado = df_carteira.copy()
        
        df_carteira_filtrado = gerar_filtros(
            df_carteira_filtrado,
            st,
            config_carteira,
            key_prefix="expander_carteira_auto"
        )

mostrar_heatmap_carteira = "Heatmap (Carteira)" in modo_mapa
mostrar_raio = "Raio (Abrangencia)" in modo_mapa


total_prestadores = df_prestadores_filtrado["id_prestador"].nunique() if "id_prestador" in df_prestadores_filtrado.columns else len(df_prestadores_filtrado)
total_carteira = df_carteira_filtrado["id_usuario"].nunique() if "id_usuario" in df_carteira_filtrado.columns else len(df_carteira_filtrado)

if raio_km > 0 and not df_prestadores_filtrado.empty:
    with st.spinner("Atualizando estatísticas de cobertura..."):
        contagens_raio = calcular_contagem_beneficiarios_raio(df_prestadores_filtrado, df_carteira_filtrado, raio_km)
else:
    contagens_raio = {}


if "last_map_center" not in st.session_state:
    st.session_state["last_map_center"] = None
if "last_map_zoom" not in st.session_state:
    st.session_state["last_map_zoom"] = None

if st.session_state["last_map_center"] and st.session_state["last_map_zoom"]:
    lat_centro = st.session_state["last_map_center"]["lat"]
    lon_centro = st.session_state["last_map_center"]["lng"]
    zoom_level = st.session_state["last_map_zoom"]
elif not df_prestadores_filtrado.empty and "latitude" in df_prestadores_filtrado.columns:
    lat_centro = df_prestadores_filtrado["latitude"].mean()
    lon_centro = df_prestadores_filtrado["longitude"].mean()

    lat_min = df_prestadores_filtrado["latitude"].min()
    lat_max = df_prestadores_filtrado["latitude"].max()
    lon_min = df_prestadores_filtrado["longitude"].min()
    lon_max = df_prestadores_filtrado["longitude"].max()

    lat_diff = lat_max - lat_min
    lon_diff = lon_max - lon_min
    max_diff = max(lat_diff, lon_diff)

    if max_diff > 5:
        zoom_level = 8
    elif max_diff > 2:
        zoom_level = 9
    elif max_diff > 1:
        zoom_level = 10
    elif max_diff > 0.5:
        zoom_level = 11
    elif max_diff > 0.2:
        zoom_level = 12
    else:
        zoom_level = 13
else:
    lat_centro, lon_centro = -22.8825, -43.4248
    zoom_level = 10.5


if "resultado_simulacao" not in st.session_state:
    st.session_state["resultado_simulacao"] = None
if "benchmark_simulacao" not in st.session_state:
    st.session_state["benchmark_simulacao"] = None

df_alvo = df_carteira_filtrado
count_unique = True
label_metric = "Carteira"

if st.session_state.get("trigger_simulacao") and not df_alvo.empty:
    with st.spinner(f"Calculando ponto sugerido ({label_metric})..."):
        ponto_otimo_novo, ponto_otimo_e = encontrar_ponto_otimo(
            df_alvo,
            raio_km,
            df_prestadores=df_prestadores_filtrado,
            count_unique=count_unique
        )
        st.session_state["resultado_simulacao"] = ponto_otimo_novo
        st.session_state["benchmark_simulacao"] = ponto_otimo_e
        st.session_state["label_metric_sim"] = label_metric
        st.session_state["trigger_simulacao"] = False

ponto_otimo_novo = st.session_state["resultado_simulacao"]
ponto_otimo_e = st.session_state["benchmark_simulacao"]
label_metric = st.session_state.get("label_metric_sim", "")

mapa = criar_mapa_base(lat_centro, lon_centro, tipo_mapa, zoom_start=zoom_level, travado=modo_travado)

if mostrar_heatmap_carteira:
    adicionar_heatmap(mapa, df_carteira_filtrado, count_unique=True)

df_prestadores_para_mapa = df_prestadores_filtrado.copy()
if contagens_raio and "id_prestador" in df_prestadores_para_mapa.columns:
    df_prestadores_para_mapa["beneficiarios_no_raio_dinamico"] = (
        df_prestadores_para_mapa["id_prestador"].map(contagens_raio)
    )

if mostrar_marcadores:
    adicionar_marcadores_prestadores(
        mapa,
        df_prestadores_para_mapa,
        raio_km=raio_km,
        total_cart=total_carteira,
        mostrar_raio=mostrar_raio,
        agrupar_marcadores=agrupar_marcadores
    )


if st.session_state["ping_location"]:
    lat_ping = st.session_state["ping_location"]["lat"]
    lon_ping = st.session_state["ping_location"]["lng"]

    metrics_ping = calcular_metricas_ponto_completas(lat_ping, lon_ping, df_carteira_filtrado, raio_km)

    info_ping = f"<b>Coordenadas:</b> {lat_ping:.4f}, {lon_ping:.4f}<br>"

    df_ref_address = df_carteira_filtrado
    address_info_ping = identificar_regiao_proxima(lat_ping, lon_ping, df_ref_address, df_geo=df_geo)

    adicionar_marcador_ping(
        mapa,
        lat_ping,
        lon_ping,
        info=info_ping,
        raio_km=raio_km if mostrar_raio else None,
        metrics=metrics_ping,
        address_info=address_info_ping
    )

if ponto_otimo_novo:
    lat_opt, lon_opt, count_opt = ponto_otimo_novo
    metrics_opt = calcular_metricas_ponto_completas(lat_opt, lon_opt, df_carteira_filtrado, raio_km)

    df_ref_address = df_carteira_filtrado
    address_info = identificar_regiao_proxima(lat_opt, lon_opt, df_ref_address, df_geo=df_geo)

    adicionar_marcador_simulacao(
        mapa,
        lat_opt,
        lon_opt,
        count_opt,
        raio_km,
        melhor_e=ponto_otimo_e,
        metric_name=label_metric,
        metrics=metrics_opt,
        address_info=address_info
    )

map_data = renderizar_mapa(mapa)

if map_data:
    if map_data.get("last_clicked"):
        clicked_loc = map_data["last_clicked"]
        if st.session_state.get("ativo_pin_clique", False):
            if st.session_state["ping_location"] != clicked_loc:
                st.session_state["ping_location"] = clicked_loc
                st.rerun()
    
    if map_data.get("zoom"):
        st.session_state["last_map_zoom"] = map_data["zoom"]
    if map_data.get("center"):
        st.session_state["last_map_center"] = map_data["center"]

if st.session_state.get("trigger_printscreen"):
    center = st.session_state.get("last_map_center", {"lat": lat_centro, "lng": lon_centro})
    zoom = st.session_state.get("last_map_zoom", zoom_level)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mapa_{timestamp}.png"
    filepath = f"printscreens/{filename}"
    
    with st.spinner("Renderizando imagem do mapa... (isso pode levar alguns segundos)"):
        m_print = criar_mapa_base(center["lat"], center["lng"], tipo_mapa, zoom_start=zoom, travado=True)
        
        if mostrar_heatmap_carteira: adicionar_heatmap(m_print, df_carteira_filtrado, count_unique=True)
        
        if mostrar_marcadores:
            adicionar_marcadores_prestadores(
                m_print, df_prestadores_para_mapa, 
                raio_km=raio_km,
                total_cart=total_carteira, 
                mostrar_raio=mostrar_raio,
                agrupar_marcadores=agrupar_marcadores
            )
        
        if st.session_state["ping_location"]:
            adicionar_marcador_ping(m_print, lat_ping, lon_ping, info=info_ping, raio_km=raio_km if mostrar_raio else None, metrics=metrics_ping, address_info=address_info_ping)
            
        if ponto_otimo_novo:
            adicionar_marcador_simulacao(m_print, lat_opt, lon_opt, count_opt, raio_km, melhor_e=ponto_otimo_e, metric_name=label_metric, metrics=metrics_opt, address_info=address_info)

        resultado = salvar_mapa_como_imagem(m_print, filepath)
        
    if resultado:
        st.session_state["ultimo_print_info"] = {
            "path": filepath,
            "filename": f"Mapa_Rede_{timestamp}.png",
            "local_name": filename
        }
    else:
        st.error("Erro técnico ao gerar printscreen.")
    
    st.session_state["trigger_printscreen"] = False
    st.rerun()



st.markdown("---")
renderizar_dashboard_carteira(df_carteira_filtrado)
st.markdown("---")
renderizar_dashboard_prestadores(df_prestadores_filtrado)


with tab_ai:
    st.markdown('<div class="ai-header"><h3 class="rainbow-text">Consultoria Estratégica</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="ai-subtitle">Análise avançada de rede e insights estratégicos.</div>', unsafe_allow_html=True)

    chat_container = st.container()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Como posso ajudar na estratégia da rede hoje?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        with st.spinner("Analisando dados..."):
            contexto_dados = generate_data_summary(
                df_prestadores_filtrado, 
                df_carteira_filtrado,
                simulation_results=st.session_state.get("resultado_simulacao"),
                benchmark_sim=st.session_state.get("benchmark_simulacao"),
                raio_km=raio_km,
                map_modes=modo_mapa
            )
            
            response = ask_agent(
                prompt,
                contexto_dados, 
                history=st.session_state.messages
            )
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(response)

    st.markdown("---")
    if st.button("Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
