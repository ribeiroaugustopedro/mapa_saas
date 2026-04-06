import pandas as pd
import numpy as np
import streamlit as st

def haversine_vectorized(lat1, lon1, lat2_array, lon2_array):
    R = 6371

    phi1, phi2 = np.radians(lat1), np.radians(lat2_array)
    dphi = np.radians(lat2_array - lat1)
    dlambda = np.radians(lon2_array - lon1)

    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c

def encontrar_ponto_otimo(df_alvo, raio_km, df_prestadores=None, count_unique=True, max_candidates=1000, grid_size_fine=25):
    if df_alvo.empty or 'latitude' not in df_alvo.columns or 'longitude' not in df_alvo.columns:
        return None, None

    coords = df_alvo.dropna(subset=['latitude', 'longitude'])
    if coords.empty:
        return None, None

    lat_data = coords['latitude'].values
    lon_data = coords['longitude'].values
    ids_data = coords['id_usuario'].values if 'id_usuario' in coords.columns and count_unique else None

    melhor_existente = None
    max_e = -1
    if df_prestadores is not None and not df_prestadores.empty:
        for _, row in df_prestadores.iterrows():
            if pd.isna(row['latitude']) or pd.isna(row['longitude']): continue
            dist = haversine_vectorized(row['latitude'], row['longitude'], lat_data, lon_data)
            mask = dist <= raio_km
            
            if count_unique and ids_data is not None:
                qtd = len(np.unique(ids_data[mask]))
            else:
                qtd = np.sum(mask)
                
            if qtd > max_e:
                max_e = qtd
                melhor_existente = (row['latitude'], row['longitude'], qtd, row.get('nome_prestador', 'Prestador'))

    if len(coords) > max_candidates:
        sampled_coords = coords.sample(n=max_candidates, random_state=42)
    else:
        sampled_coords = coords

    candidatos_lat = sampled_coords['latitude'].values
    candidatos_lon = sampled_coords['longitude'].values

    if df_prestadores is not None and not df_prestadores.empty:
        p_coords = df_prestadores.dropna(subset=['latitude', 'longitude'])
        candidatos_lat = np.concatenate([candidatos_lat, p_coords['latitude'].values])
        candidatos_lon = np.concatenate([candidatos_lon, p_coords['longitude'].values])

    melhor_global_novo = None
    max_global_novo = -1

    for i in range(len(candidatos_lat)):
        lt, ln = candidatos_lat[i], candidatos_lon[i]
        dist = haversine_vectorized(lt, ln, lat_data, lon_data)
        mask = dist <= raio_km
        
        if count_unique and ids_data is not None:
            qtd = len(np.unique(ids_data[mask]))
        else:
            qtd = np.sum(mask)
        
        if qtd > max_global_novo:
            max_global_novo = qtd
            melhor_global_novo = (lt, ln)

    if not melhor_global_novo:
        return None, melhor_existente

    delta_lat = 0.005
    delta_lon = 0.005
    
    lats_f = np.linspace(melhor_global_novo[0] - delta_lat, melhor_global_novo[0] + delta_lat, grid_size_fine)
    lons_f = np.linspace(melhor_global_novo[1] - delta_lon, melhor_global_novo[1] + delta_lon, grid_size_fine)
    
    melhor_final_novo = melhor_global_novo
    max_final_novo = max_global_novo

    for lat_f in lats_f:
        for lon_f in lons_f:
            dist = haversine_vectorized(lat_f, lon_f, lat_data, lon_data)
            mask = dist <= raio_km
            
            if count_unique and ids_data is not None:
                qtd = len(np.unique(ids_data[mask]))
            else:
                qtd = np.sum(mask)
            
            if qtd > max_final_novo:
                max_final_novo = qtd
                melhor_final_novo = (lat_f, lon_f)

    return (melhor_final_novo[0], melhor_final_novo[1], max_final_novo), melhor_existente

def gerar_filtros(
    df: pd.DataFrame,
    container,
    config_filtros: list[dict],
    key_prefix: str = "filtro"
) -> pd.DataFrame:
    df_filtrado = df.copy()
    
    if not config_filtros:
        return df_filtrado

    for config in config_filtros:
        col = config.get("col")
        if col not in df.columns:
            continue
            
        label = config.get("label", col.replace("_", " ").title())
        multivalue = config.get("multivalue", False)
        separator = config.get("separator", "|")
        
        if multivalue:
            s_list = (
                df_filtrado[col]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.split(separator)
                .apply(lambda xs: {x.strip() for x in xs if x and x.strip()})
            )
            opcoes = sorted(set().union(*s_list.tolist())) if len(s_list) else []
        else:
            opcoes = sorted(df_filtrado[col].dropna().astype(str).unique())

        key = f"{key_prefix}_{col}"

        selecionados = container.multiselect(f"{label}", opcoes, key=key)
        
        if selecionados:
            if multivalue:
                selecionados_set = {x.upper().strip() for x in selecionados}
                mask = s_list.apply(lambda s: bool(s.intersection(selecionados_set)))
                df_filtrado = df_filtrado[mask]
            else:
                df_filtrado = df_filtrado[df_filtrado[col].astype(str).isin(selecionados)]

    return df_filtrado

def detectar_colunas_filtro(
    df: pd.DataFrame, 
    colunas_ignoradas: list[str] | None = None,
    separador_multivalor: str = "|"
) -> list[dict]:
    if colunas_ignoradas is None:
        colunas_ignoradas = []
        
    config_gerada = []
    
    ignorados_set = {c.lower() for c in colunas_ignoradas}
    
    for col in df.columns:
        if col.lower() in ignorados_set:
            continue
            
        if df[col].isnull().all():
            continue

        dtype_str = str(df[col].dtype)
        if not ("object" in dtype_str or "string" in dtype_str or "category" in dtype_str):
            continue
            
        amostra = df[col].dropna().astype(str)
        if amostra.empty:
            continue
            
        tem_separador = amostra.head(100).str.contains(separador_multivalor, regex=False).any()
        
        label_base = col.replace("_usuario", "").replace("_", " ")
        label_base = label_base[0].upper() + label_base[1:].lower() if label_base else ""
        
        label_correcoes = {
            "Classificacao": "Classificação",
            "Regiao": "Região",
            "Prestacao": "Prestação",
            "Atencao": "Atenção",
            "Situacao": "Situação",
            "Inscricao": "Inscrição",
            "Operacao": "Operação",
            "Localizacao": "Localização",
            "Informacao": "Informação",
            "Especializacao": "Especialização",
            "Codigo": "Código",
            "Historico": "Histórico",
            "Medico": "Médico",
            "Clinico": "Clínico",
            "Cirurgico": "Cirúrgico",
            "Pediatrico": "Pediátrico",
            "Ginecologico": "Ginecológico",
            "Ortopedico": "Ortopédico",
            "Cardiologico": "Cardiológico",
            "Neurologico": "Neurológico",
            "Psicologico": "Psicológico",
            "Farmaceutico": "Farmacêutico",
            "Genetico": "Genético",
            "Estetico": "Estético",
            "Area": "Área",
            "Nucleo": "Núcleo",
            "Orgao": "Órgão",
            "Periodo": "Período",
            "Numero": "Número",
            "Sequencia": "Sequência",
            "Frequencia": "Frequência",
            "Ocorrencia": "Ocorrência",
            "Referencia": "Referência",
            "Preferencia": "Preferência",
            "Experiencia": "Experiência",
            "Beneficiario": "Beneficiário",
            "Usuario": "Usuário",
            "Funcionario": "Funcionário",
            "Secretaria": "Secretária",
            "Primario": "Primário",
            "Secundario": "Secundário",
            "Terciario": "Terciário",
            "Temporario": "Temporário",
            "Necessario": "Necessário",
            "Voluntario": "Voluntário",
            "Etaria": "Etária",
            "Saude": "Saúde",
            "Unica": "Única",
            "Unico": "Único",
            "Basico": "Básico",
            "Basica": "Básica",
            "Publico": "Público",
            "Publica": "Pública",
            "Especifico": "Específico",
            "Especifica": "Específica",
            "Grafico": "Gráfico",
            "Grafica": "Gráfica",
            "Geografico": "Geográfico",
            "Geografica": "Geográfica",
            "Economico": "Econômico",
            "Economica": "Econômica",
            "Tecnico": "Técnico",
            "Tecnica": "Técnica",
            "Pratico": "Prático",
            "Pratica": "Prática",
            "Critico": "Crítico",
            "Critica": "Crítica",
            "Logico": "Lógico",
            "Logica": "Lógica",
            "Fisico": "Físico",
            "Fisica": "Física",
            "Quimico": "Químico",
            "Quimica": "Química",
            "Biologico": "Biológico",
            "Biologica": "Biológica",
            "Agrupada": "agrupada"
        }
        
        for errado, correto in label_correcoes.items():
            label_base = label_base.replace(errado, correto)
        
        config_gerada.append({
            "col": col,
            "label": label_base,
            "multivalue": bool(tem_separador),
            "separator": separador_multivalor
        })
        
    return config_gerada

def salvar_mapa_como_imagem(mapa, output_path):
    """
    Tenta salvar um mapa Folium como imagem PNG usando Playwright ou Selenium.
    """
    import os
    import tempfile
    import time
    
    print(f"Iniciando captura de mapa para: {output_path}")
    
    # Criar pasta se não existir
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Salvar mapa em HTML temporário
    tmp_name = f"map_temp_{int(time.time())}.html"
    tmp_html = os.path.join(tempfile.gettempdir(), tmp_name)
    try:
        mapa.save(tmp_html)
        print(f"HTML temporário salvo em: {tmp_html}")
    except Exception as e:
        print(f"Erro ao salvar HTML temporário: {e}")
        return False
    
    success = False
    
    try:
        print("Tentando captura via Playwright...")
        import asyncio
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1600, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                extra_http_headers={"Referer": "http://localhost:8501/"}
            )
            page = context.new_page()
            file_url = f"file:///{os.path.abspath(tmp_html).replace('\\', '/')}"
            page.goto(file_url, wait_until="networkidle")
            time.sleep(2)
            page.screenshot(path=output_path, full_page=True)
            browser.close()
            success = True
            print("Captura via Playwright concluída com sucesso.")
    except Exception as e:
        print(f"Falha no Playwright: {e}")
        # Tenta Selenium (Clássico)
        try:
            print("Tentando captura via Selenium...")
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--window-size=1600,800")
            
            driver = webdriver.Chrome(options=chrome_options)
            file_url = f"file:///{os.path.abspath(tmp_html).replace('\\', '/')}"
            driver.get(file_url)
            time.sleep(3)
            driver.save_screenshot(output_path)
            driver.quit()
            success = True
            print("Captura via Selenium concluída com sucesso.")
        except Exception as e2:
            print(f"Falha no Selenium: {e2}")
    
    # Limpar HTML temporário
    try:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)
    except:
        pass
        
    return success
    
    # Limpar HTML temporário
    try:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)
    except:
        pass
        
    return success