import pandas as pd
import streamlit as st
import os
import google.generativeai as genai

def generate_data_summary(df_providers, df_members, simulation_results=None, benchmark_sim=None, radius_km=5, map_modes=[]):
    summary = []
    
    summary.append(f"### Analysis Configuration")
    summary.append(f"- **Radius**: {radius_km} km")
    summary.append(f"- **Active Layers**: {', '.join(map_modes) if map_modes else 'Markers Only'}")
    
    n_providers = len(df_providers)
    
    # Standardized ID detection
    col_id = 'user_id' if 'user_id' in df_members.columns else 'member_id' if 'member_id' in df_members.columns else None
    n_members = df_members[col_id].nunique() if col_id else len(df_members)
    
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
        return "Configuration Error: Gemini API key missing. Please ensure GEMINI_API_KEY is set in environment variables or .streamlit/secrets.toml."
        
    try:
        genai.configure(api_key=api_key)
        
        # Cache model selection to save API calls and quota
        if "selected_model" not in st.session_state:
            available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            priority_models = [
                "models/gemini-1.5-flash-latest",
                "models/gemini-1.5-flash",
                "models/gemini-pro"
            ]
            selected = None
            for target in priority_models:
                if target in available_models:
                    selected = target
                    break
            st.session_state["selected_model"] = selected or (available_models[0] if available_models else "models/gemini-1.5-flash")

        model = genai.GenerativeModel(
            model_name=st.session_state["selected_model"],
            system_instruction=(
                "You are the Strategic Network Director. "
                "Tone: Highly professional, senior, executive, and analytical. "
                "No emojis or emoticons allowed. "
                "Use Title Case for diagnostic sections. Be precise and cite context data."
            )
        )

        chat_history = []
        for msg in history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        valid_history = chat_history[:-1] if chat_history else None
        chat = model.start_chat(history=valid_history)
        
        prompt = f"Data Context:\n{context_summary}\n\nExecutive Query: {user_question}"
        
        response = chat.send_message(prompt)
        return response.text
        
    except Exception as e:
        error_msg = str(e).upper()
        if "429" in error_msg or "QUOTA" in error_msg or "EXHAUSTED" in error_msg:
            return "Quota Limit Reached: The free tier is currently at capacity. Please wait 60 seconds."
        if "API" in error_msg and "KEY" in error_msg and "INVALID" in error_msg:
            return "Configuration Error: The Gemini API Key was rejected as invalid. Please check your secrets.toml."
        return f"Strategic AI Engine Error: {str(e)}"
