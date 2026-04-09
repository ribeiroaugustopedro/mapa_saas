import pandas as pd
import streamlit as st
import os
import time
import google.generativeai as genai
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

def ask_agent(user_question, context_summary, history=[]):
    """Diagnoses and attempts AI connection using 2.5/2.0 models."""
    api_key = st.secrets.get("gemini", {}).get("api_key") or os.getenv("GEMINI_API_KEY")
    if not api_key: return "API Key Configuration Missing."

    # Verified list from diagnosis
    priority_models = [
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
        "models/gemini-pro-latest"
    ]

    last_err_msg = ""
    for model_name in priority_models:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # Lite prompt
            prompt = f"Data: {context_summary}\nAnalyze: {user_question}"
            response = model.generate_content(prompt)
            
            if response.text:
                return response.text
        except Exception as e:
            last_err_msg = str(e)
            if any(x in last_err_msg.upper() for x in ["429", "503", "QUOTA", "LIMIT"]):
                time.sleep(1)
                continue
            continue
            
    # Return both the capacity warning AND the diagnostic for direct visibility
    return f"Strategic Advisory at capacity. (Diagnostic: {last_err_msg})"

def generate_data_summary(df_providers, df_members, simulation_results=None, benchmark_sim=None, radius_km=5, map_modes=[]):
    return f"Network: {len(df_providers)}. Members: {len(df_members):,}."
