import pandas as pd
import streamlit as st
import duckdb
from pathlib import Path

@st.cache_data(ttl=3600, show_spinner=False)
def load_processed_data():
    try:
        # Check for Motherduck token in Streamlit config or ENV variable
        token = None
        try:
            if "motherduck" in st.secrets and "MOTHERDUCK_TOKEN" in st.secrets.motherduck:
                token = st.secrets.motherduck.MOTHERDUCK_TOKEN
        except FileNotFoundError:
            pass
            
        import os
        if not token:
            token = os.getenv("MOTHERDUCK_TOKEN")
            
        if token:
            con = duckdb.connect(f'md:?motherduck_token={token}', read_only=True)
        else:
            # FORCE ABSOLUTE PATH TO PREVENT SYNC ISSUES
            db_path = "c:/Users/Pedro Augusto/OneDrive/Área de Trabalho/linux/data_warehouse/duckdb/warehouse.db"
            import os
            if not os.path.exists(db_path):
                raise FileNotFoundError(f"Warehouse not found at {db_path}")
                
            con = duckdb.connect(db_path, read_only=True)
        
        # Load DataFrames from Gold Layer
        df_members = con.execute("SELECT * FROM gold.members").df()
        df_providers = con.execute("SELECT * FROM gold.providers").df()
        
        # Explicitly ensure uppercase for all object columns (Safety Layer)
        for df in [df_members, df_providers]:
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.upper()

        con.close()
            
        return df_providers, df_members
    except Exception as e:
        st.error(f"Error loading warehouse data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def get_data():
    return load_processed_data()

@st.cache_data(ttl=600)
def get_filtered_heatmap_grid(filter_sql="1=1"):
    """High-speed gridded aggregation cache."""
    db_path = "c:/Users/Pedro Augusto/OneDrive/Área de Trabalho/linux/data_warehouse/duckdb/warehouse.db"
    conn = duckdb.connect(db_path, read_only=True)
    try:
        query = f"""
            SELECT 
                ROUND(loc_latitude, 2) as lat,
                ROUND(loc_longitude, 2) as lon,
                COUNT(*) as weight
            FROM gold.members
            WHERE {filter_sql}
            GROUP BY 1, 2
        """
        return conn.execute(query).df()
    finally:
        conn.close()
