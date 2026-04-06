import pandas as pd
import streamlit as st
import duckdb
from pathlib import Path

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_dados_processados():
    try:
        # 1. Tenta caminho local (Self-contained repo)
        db_path = Path("dataset/warehouse.db").resolve()
        
        # 2. Fallback para warehouse paralelo (ambiente dev local)
        if not db_path.exists():
            db_path = Path("../warehouse/duckdb/warehouse.db").resolve()
            
        if not db_path.exists():
            raise FileNotFoundError(f"Warehouse DuckDB não encontrado. Verifique a pasta dataset/ ou warehouse/.")
            
        con = duckdb.connect(str(db_path), read_only=True)
        
        # Load DataFrames from Gold Layer
        df_carteira = con.execute("SELECT * FROM gold.carteira").df()
        df_prestadores = con.execute("SELECT * FROM gold.prestadores").df()
        df_geo = con.execute("SELECT * FROM gold.geolocalizacao").df()
        
        con.close()
            
        return df_prestadores, df_carteira, df_geo
    except Exception as e:
        st.error(f"Erro ao carregar dados do warehouse: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def get_data():
    return carregar_dados_processados()
