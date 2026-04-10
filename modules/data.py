import pandas as pd
import streamlit as st
import duckdb
import os
from modules.utils import detect_filter_columns

@st.cache_data(ttl=3600, show_spinner=False)
def load_processed_data():
    try:
        token = None
        try:
            if "motherduck" in st.secrets and "MOTHERDUCK_TOKEN" in st.secrets.motherduck:
                token = st.secrets.motherduck.MOTHERDUCK_TOKEN
        except: pass
        if not token: token = os.getenv("MOTHERDUCK_TOKEN")
        if not token: return pd.DataFrame(), pd.DataFrame()
        con = duckdb.connect(f'md:?motherduck_token={token}', read_only=True)
        df_members = con.execute("SELECT * FROM gold.members").df()
        df_providers = con.execute("SELECT * FROM gold.providers").df()
        for df in [df_members, df_providers]:
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.upper()
        con.close()
        return df_providers, df_members
    except:
        return pd.DataFrame(), pd.DataFrame()

def load_all_data():
    df_providers, df_members = load_processed_data()
    # Adding precise ignored columns based on user request
    ignored_portfolio = [
        'loc_latitude', 'loc_longitude', 'user_id', 'member_id', 
        'loc_neighborhood', 'loc_zip_code', 'neighborhood', 'zip_code'
    ]
    ignored_providers = [
        'loc_latitude', 'loc_longitude', 'prov_id', 'prov_latitude', 'prov_longitude',
        'loc_neighborhood', 'loc_zip_code', 'prov_name', 'prov_tax_id', 'name', 'tax_id'
    ]
    config_portfolio = detect_filter_columns(df_members, ignored_columns=ignored_portfolio)
    config_providers = detect_filter_columns(df_providers, ignored_columns=ignored_providers)
    return df_members, df_providers, config_providers, config_portfolio

def get_data():
    return load_processed_data()

@st.cache_data(ttl=600)
def get_filtered_heatmap_grid(filter_sql="1=1"):
    token = None
    try:
        if "motherduck" in st.secrets and "MOTHERDUCK_TOKEN" in st.secrets.motherduck:
            token = st.secrets.motherduck.MOTHERDUCK_TOKEN
    except: pass
    if not token: token = os.getenv("MOTHERDUCK_TOKEN")
    if not token: return pd.DataFrame()
    try:
        conn = duckdb.connect(f'md:?motherduck_token={token}', read_only=True)
        query = f"""
            SELECT 
                ROUND(loc_latitude, 2) as lat,
                ROUND(loc_longitude, 2) as lon,
                COUNT(*) as weight
            FROM gold.members
            WHERE {filter_sql}
            GROUP BY 1, 2
        """
        df = conn.execute(query).df()
        conn.close()
        return df
    except:
        return pd.DataFrame()
