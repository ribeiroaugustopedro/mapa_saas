import pandas as pd
import streamlit as st
import duckdb
from pathlib import Path

@st.cache_data(ttl=10, show_spinner=False)
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
            # Try centralized path (parallel data_warehouse)
            db_path = Path(__file__).parent.parent.parent / "data_warehouse/duckdb/warehouse.db"
            db_path = db_path.resolve()
            
            if not db_path.exists():
                raise FileNotFoundError(f"MOTHERDUCK_TOKEN not found and local DuckDB Warehouse not found at {db_path}")
                
            con = duckdb.connect(str(db_path), read_only=True)
        
        # Load DataFrames from Gold Layer
        df_members = con.execute("SELECT * FROM gold.members").df()
        df_providers = con.execute("SELECT * FROM gold.providers").df()
        
        con.close()
            
        return df_providers, df_members
    except Exception as e:
        st.error(f"Error loading warehouse data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def get_data():
    return load_processed_data()
