import pandas as pd
import streamlit as st
import os
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def generate_data_summary(df_providers, df_members, simulation_results=None, benchmark_sim=None, radius_km=5, map_modes=[]):
    summary = []
    
    summary.append(f"### Analysis Configuration")
    summary.append(f"- **Radius**: {radius_km} km")
    summary.append(f"- **Active Layers**: {', '.join(map_modes) if map_modes else 'Markers Only'}")
    
    n_providers = len(df_providers)
    n_members = df_members['member_id'].nunique() if 'member_id' in df_members.columns else len(df_members)
    
    summary.append(f"### Overview")
    summary.append(f"- **Total Providers**: {n_providers}")
    summary.append(f"- **Total Member Base**: {n_members}")

    if simulation_results:
        lat_opt, lon_opt, count_opt = simulation_results
        summary.append(f"### Simulation Results")
        summary.append(f"- **Recommended Point**: ({lat_opt:.4f}, {lon_opt:.4f})")
        summary.append(f"- **Potential Reach**: {count_opt:,} members in {radius_km}km radius")
        
        if benchmark_sim:
            lat_e, lon_e, count_e, nome_e = benchmark_sim
            diff = count_opt - count_e
            perc = (count_opt / count_e - 1) * 100 if count_e > 0 else 0
            summary.append(f"- **Benchmark vs Best Current ({nome_e})**: {'Improvement' if diff > 0 else 'Difference'} of **{diff:,}** ({perc:+.1f}%)")
    
    summary.append(f"### Geography")
    
    if 'loc_region' in df_providers.columns:
        top_reg_prest = df_providers['loc_region'].value_counts().head(5).to_dict()
        summary.append(f"- **Top 5 Regions (Network)**: {top_reg_prest}")
        
    if 'prov_type' in df_providers.columns:
        types = df_providers['prov_type'].value_counts().to_dict()
        summary.append(f"- **Network Profile (Types)**: {types}")
        
    summary.append(f"### Member Profile")
    if 'user_age_group' in df_members.columns:
        age_dist = df_members['user_age_group'].value_counts().head(5).to_dict()
        summary.append(f"- **Age Distribution**: {age_dist}")
    
    if 'contract_product' in df_members.columns:
        prod_dist = df_members['contract_product'].value_counts().head(5).to_dict()
        summary.append(f"- **Main Products**: {prod_dist}")

    return "\n".join(summary)

def configure_gemini():
    api_key = None
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        api_key = st.secrets["gemini"]["api_key"]
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    return api_key

def ask_agent(user_question, context_summary, history=[]):
    api_key = configure_gemini()
    
    if not api_key:
        return "Configuration Error: Gemini API key missing. Please check your environment variables or Streamlit secrets."
        
    genai.configure(api_key=api_key)
    
    # 100% Free Version: Gemini 1.5 Flash
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 2048,
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction=(
            "You are the Strategic Network Director. "
            "Tone: Highly professional, senior, executive, and analytical. "
            "No emojis or emoticons allowed. "
            "Use Title Case for your diagnostic sections: 'Situational Diagnosis', 'Critical Insights', 'Strategic Recommendations'. "
            "Be precise, cite context data, and never invent metrics."
        )
    )

    chat_history = []
    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [msg["content"]]})

    try:
        chat = model.start_chat(history=chat_history[:-1] if chat_history else None)
        
        prompt = f"Data Context:\n{context_summary}\n\nExecutive Query: {user_question}"
        
        response = chat.send_message(prompt)
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return "Quota Limit Reached: Please wait a moment (429 Resource Exhausted)."
        return f"AI Service Error: {error_msg}"
