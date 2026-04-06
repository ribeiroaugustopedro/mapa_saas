import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
from modules.utils import haversine_vectorized

@st.cache_data
def calcular_cobertura_prestadores(df_prestadores, df_carteira, raio_km):
    if df_prestadores.empty:
        return None, pd.DataFrame()

    if 'latitude' not in df_prestadores.columns or 'longitude' not in df_prestadores.columns:
        return None, pd.DataFrame()

    cart_coords = df_carteira.dropna(subset=['latitude', 'longitude'])[['latitude', 'longitude']] if not df_carteira.empty else pd.DataFrame()
    
    resultados = []

    total_carteira = df_carteira['id_usuario'].nunique() if not df_carteira.empty and 'id_usuario' in df_carteira.columns else len(df_carteira)

    for idx, row in df_prestadores.iterrows():
        lat_p = row['latitude']
        lon_p = row['longitude']
        
        if pd.isna(lat_p) or pd.isna(lon_p):
            continue
        
        metrics = {
            "carteira": 0,
            "total_carteira": total_carteira
        }
        
        if not cart_coords.empty:
            dist_c = haversine_vectorized(lat_p, lon_p, cart_coords['latitude'].values, cart_coords['longitude'].values)
            mask_c = dist_c <= raio_km
            if 'id_usuario' in df_carteira.columns:
                metrics["carteira"] = df_carteira.loc[cart_coords.index[mask_c], 'id_usuario'].nunique()
            else:
                metrics["carteira"] = np.sum(mask_c)

        resultados.append({
            "nome_prestador": row.get("nome_prestador", "Desconhecido"),
            "id_prestador": row.get("id_prestador", idx),
            "cobertura": metrics["carteira"], 
            "metrics": metrics,
            "tipo_prestador": row.get("tipo_prestador", "N/A")
        })
    
    if not resultados:
        return None, pd.DataFrame()
        
    df_res = pd.DataFrame(resultados)
    melhor_row = df_res.loc[df_res['cobertura'].idxmax()] if not df_res.empty else None
    
    return melhor_row, df_res

@st.cache_data
def calcular_contagem_beneficiarios_raio(df_prestadores, df_carteira, raio_km):
    _, df_res = calcular_cobertura_prestadores(df_prestadores, df_carteira, raio_km)
    
    if df_res.empty:
        return {}
        
    return df_res.set_index('id_prestador')['metrics'].to_dict()

def calcular_metricas_ponto_completas(lat, lon, df_carteira, raio_km):
    total_carteira = df_carteira['id_usuario'].nunique() if not df_carteira.empty and 'id_usuario' in df_carteira.columns else len(df_carteira)

    res = {
        "carteira": 0,
        "total_carteira": total_carteira
    }
    
    if not df_carteira.empty and "latitude" in df_carteira.columns:
        coords_c = df_carteira.dropna(subset=['latitude', 'longitude'])
        if not coords_c.empty:
            dist = haversine_vectorized(lat, lon, coords_c['latitude'].values, coords_c['longitude'].values)
            mask = dist <= raio_km
            if 'id_usuario' in df_carteira.columns:
                res["carteira"] = coords_c.loc[mask, 'id_usuario'].nunique()
            else:
                res["carteira"] = np.sum(mask)

    return res

def identificar_regiao_proxima(lat, lon, df_ref, df_geo=None):
    if df_geo is not None and not df_geo.empty:
        cols_loc = ['latitude', 'longitude']
        if all(c in df_geo.columns for c in cols_loc):
             df_valid = df_geo.dropna(subset=cols_loc)
             if not df_valid.empty:
                lats = df_valid['latitude'].values
                lons = df_valid['longitude'].values
                dists = haversine_vectorized(lat, lon, lats, lons)
                idx_min = np.argmin(dists)
                
                row = df_valid.iloc[idx_min]
                
                info = {}
                if 'regiao' in row: info['Região'] = row['regiao']
                
                if 'cidade' in row: info['Município'] = row['cidade']
                
                if 'bairro' in row: info['Bairro'] = row['bairro']
                
                if 'cep' in row: 
                    try:
                        c_val = str(int(float(row['cep']))).replace('.', '')
                        c_val = c_val.zfill(8)
                        info['CEP'] = f"{c_val[:5]}-{c_val[5:]}"
                    except:
                        info['CEP'] = row['cep']

                return info

    if df_ref.empty:
        return {}
        
    cols_loc = ['latitude', 'longitude']
    if not all(c in df_ref.columns for c in cols_loc):
        return {}
        
    df_valid = df_ref.dropna(subset=cols_loc)
    if df_valid.empty:
        return {}
        
    lats = df_valid['latitude'].values
    lons = df_valid['longitude'].values
    dists = haversine_vectorized(lat, lon, lats, lons)
    idx_min = np.argmin(dists)
    
    row = df_valid.iloc[idx_min]
    
    info = {}
    
    col_mapping = {
        'Região Agrupada': ['regiao_agrupada', 'regiao_agrupada_usuario'],
        'Região': ['regiao', 'regiao_usuario'],
        'Município': ['municipio', 'municipio_usuario', 'cidade', 'cidade_usuario'],
        'Bairro': ['bairro', 'bairro_usuario']
    }
    
    for display_key, candidate_cols in col_mapping.items():
        for col_name in candidate_cols:
            if col_name in row:
                val = row[col_name]
                if pd.notna(val) and str(val).strip() != "":
                    info[display_key] = val
                    break
    
    cep_cols = ['cep', 'cep_usuario']
    for c in cep_cols:
        if c in row:
            val = row[c]
            if pd.notna(val):
                try:
                    c_val = str(int(float(val))).zfill(8)
                    info['CEP'] = f"{c_val[:5]}-{c_val[5:]}"
                    break
                except:
                    pass

    return info

def render_kpi_card(title, value, subtext="", color=None):
    # If no color, use rainbow text
    value_class = "card-value rainbow-text" if not color else "card-value"
    val_style = f'style="color: {color} !important;"' if color else ""
    
    st.markdown(f"""
    <div class="dashboard-card" title="{value}">
        <div class="card-title">{title}</div>
        <div class="card-value-container">
            <div class="{value_class}" {val_style}>{value}</div>
        </div>
        <div class="card-subtext">{subtext}</div>
    </div>
    """, unsafe_allow_html=True)

def apply_chart_theme(chart, title=None):
    if title:
        chart = chart.properties(title=alt.TitleParams(text=title, anchor='start', fontSize=14, fontWeight=600, dy=-10))
    
    return chart.properties(
        width='container'
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        gridColor="#555" if st.get_option("theme.base") == "dark" else "#eee",
        gridDash=[3,3],
        labelFontSize=10,
        titleFontSize=11,
        titleFontWeight=400,
        labelColor="#999" if st.get_option("theme.base") == "dark" else "#666",
        titleColor="#999" if st.get_option("theme.base") == "dark" else "#666"
    ).configure_legend(
        labelColor="#999" if st.get_option("theme.base") == "dark" else "#666",
        titleColor="#999" if st.get_option("theme.base") == "dark" else "#666"
    )

def render_bar_chart(df, x_col, y_col, color, title, label_fmt=",.0f", horizontal=True):
    if df.empty:
        st.info(f"Dados insuficientes para: {title}")
        return

    x_axis = alt.X(f"{x_col}:Q", title=None, axis=alt.Axis(labels=False, grid=False))
    y_axis = alt.Y(f"{y_col}:N", sort="-x" if horizontal else None, title=None, axis=alt.Axis(labelLimit=150))
    
    if not horizontal:
        x_axis, y_axis = alt.X(f"{y_col}:N", title=None), alt.Y(f"{x_col}:Q", title=None, axis=alt.Axis(labels=False, grid=False))

    base = alt.Chart(df).encode(
        x=x_axis,
        y=y_axis,
        tooltip=[y_col, alt.Tooltip(x_col, format=label_fmt)]
    )

    bars = base.mark_bar(color=color, cornerRadiusEnd=4, opacity=0.8)
    
    text_color = "white" if st.get_option("theme.base") == "dark" else "#333"
    labels = base.mark_text(
        align='left' if horizontal else 'center',
        baseline='middle' if horizontal else 'bottom',
        dx=5 if horizontal else 0,
        dy=0 if horizontal else -5,
        color=text_color,
        fontSize=10,
        fontWeight=500
    ).encode(
        text=alt.Text(f"{x_col}:Q", format=label_fmt)
    )

    chart = (bars + labels).properties(height=280)
    st.altair_chart(apply_chart_theme(chart, title), use_container_width=True)

def renderizar_dashboard_carteira(df_carteira):
    if df_carteira.empty:
        return

    # Using Portfolio Accent Colors for charts
    chart_color = "#2563eb" if st.get_option("theme.base") == "light" else "#64ffda"
    st.markdown(f"<h2 class='rainbow-text-simple' style='font-family: \"Fira Code\", monospace;'>Carteira</h2>", unsafe_allow_html=True)
    
    total_carteira = df_carteira['id_usuario'].nunique() if 'id_usuario' in df_carteira.columns else len(df_carteira)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Carteira", f"{total_carteira:,}", "Beneficiarios")
    with k2: 
        top_p = "-"
        if "produto" in df_carteira.columns and not df_carteira["produto"].empty:
            top_p = df_carteira["produto"].value_counts().index[0]
        render_kpi_card("Top Produto", top_p, "Volume")
    with k3:
        top_r = "-"
        if "regiao_usuario" in df_carteira.columns and not df_carteira["regiao_usuario"].empty:
            top_r = df_carteira["regiao_usuario"].value_counts().index[0]
        render_kpi_card("Regiao Principal", top_r, "Presenca")
    with k4:
        top_f = "-"
        if "faixa_etaria" in df_carteira.columns and not df_carteira["faixa_etaria"].empty:
            top_f = df_carteira["faixa_etaria"].value_counts().index[0]
        render_kpi_card("Idade Media (Moda)", top_f, "Perfil")

    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        reg_col = "regiao_agrupada_usuario" if "regiao_agrupada_usuario" in df_carteira.columns else "regiao_agrupada"
        if reg_col in df_carteira.columns:
            df_reg_ag = df_carteira.groupby(reg_col)["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_reg_ag.sort_values("qtd", ascending=False).head(10), "qtd", reg_col, chart_color, "Região Agrupada")
    with c2:
        if "regiao_usuario" in df_carteira.columns:
            df_reg = df_carteira.groupby("regiao_usuario")["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_reg.sort_values("qtd", ascending=False).head(10), "qtd", "regiao_usuario", chart_color, "Região")

    c3, c4 = st.columns(2)
    with c3:
        class_col = "classificacao_produto"
        if class_col in df_carteira.columns:
            df_class = df_carteira.groupby(class_col)["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_class.sort_values("qtd", ascending=False).head(10), "qtd", class_col, chart_color, "Classificação Produto")
    with c4:
        if "produto" in df_carteira.columns:
            df_prod = df_carteira.groupby("produto")["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_prod.sort_values("qtd", ascending=False).head(8), "qtd", "produto", chart_color, "Produto")

    c5, c6 = st.columns(2)
    with c5:
        if "faixa_etaria" in df_carteira.columns:
            df_age = df_carteira.groupby("faixa_etaria")["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_age, "qtd", "faixa_etaria", chart_color, "Faixa Etária")
    with c6:
        if "pool_risco" in df_carteira.columns:
            df_pool = df_carteira.groupby("pool_risco")["id_usuario"].nunique().reset_index(name="qtd")
            render_bar_chart(df_pool, "qtd", "pool_risco", chart_color, "Pool de Risco")


def renderizar_dashboard_prestadores(df_prestadores):
    if df_prestadores.empty:
        return

    chart_color = "#2563eb" if st.get_option("theme.base") == "light" else "#64ffda"
    st.markdown(f"<h2 class='rainbow-text-simple' style='font-family: \"Fira Code\", monospace;'>Prestadores</h2>", unsafe_allow_html=True)
    
    total_p = len(df_prestadores)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Rede Total", f"{total_p}", "Prestadores")
    with k2: 
        top_t = "-"
        if "tipo_prestador" in df_prestadores.columns and not df_prestadores["tipo_prestador"].empty:
            top_t = df_prestadores["tipo_prestador"].value_counts().index[0]
        render_kpi_card("Segmento Lider", top_t, "Volume")
    with k3:
        top_r = "-"
        if "regiao" in df_prestadores.columns and not df_prestadores["regiao"].empty:
            top_r = df_prestadores["regiao"].value_counts().index[0]
        render_kpi_card("Centro de Rede", top_r, "Concentracao")
    with k4:
        status = "-"
        if "ie_prestador" in df_prestadores.columns and not df_prestadores["ie_prestador"].empty:
             status = df_prestadores["ie_prestador"].value_counts().index[0]
        render_kpi_card("Status Principal", status, "Predominante")

    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        if "regiao" in df_prestadores.columns:
            df_reg = df_prestadores.groupby("regiao").size().reset_index(name="qtd")
            render_bar_chart(df_reg.sort_values("qtd", ascending=False).head(10), "qtd", "regiao", chart_color, "Região")
    with c2:
        if "tipo_prestador" in df_prestadores.columns:
            df_tipo = df_prestadores.groupby("tipo_prestador").size().reset_index(name="qtd")
            render_bar_chart(df_tipo, "qtd", "tipo_prestador", chart_color, "Tipo de Prestador")

    c3, c4 = st.columns(2)
    with c3:
        if "municipio" in df_prestadores.columns:
            df_mun = df_prestadores.groupby("municipio").size().reset_index(name="qtd")
            render_bar_chart(df_mun.sort_values("qtd", ascending=False).head(10), "qtd", "municipio", chart_color, "Município")
    with c4:
        if "ie_prestador" in df_prestadores.columns:
            df_status = df_prestadores.groupby("ie_prestador").size().reset_index(name="qtd")
            render_bar_chart(df_status, "qtd", "ie_prestador", chart_color, "Status")
