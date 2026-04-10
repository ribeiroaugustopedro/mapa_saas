import pandas as pd
import streamlit as st
import os
import time
import google.generativeai as genai
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

def ask_agent(user_question, context_summary, history=[]):
    api_key = st.secrets.get("gemini", {}).get("api_key") or os.getenv("GEMINI_API_KEY")
    if not api_key: return "API Key Configuration Missing."
    priority_models = ["models/gemini-2.0-flash", "models/gemini-flash-latest", "models/gemini-pro-latest"]
    last_err_msg = ""
    for model_name in priority_models:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(f"Data: {context_summary}\nAnalyze: {user_question}")
            if response.text: return response.text
        except Exception as e:
            last_err_msg = str(e)
            if any(x in last_err_msg.upper() for x in ["429", "503", "QUOTA", "LIMIT"]):
                time.sleep(1)
                continue
    return f"Strategic Advisory at capacity. (Diagnostic: {last_err_msg})"

def generate_data_summary(df_providers, df_members):
    return f"Network Points: {len(df_providers)}. Portfolio Size: {len(df_members):,} members."

def render_ai_advisor(df_members, df_providers):
    st.markdown("##### 🕵️ Strategic Advisory (BETA)")
    if "ai_chat_history" not in st.session_state: st.session_state.ai_chat_history = []
    
    for chat in st.session_state.ai_chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    if prompt := st.chat_input("Explore Network Patterns..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.ai_chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Running deep analysis..."):
                summary = generate_data_summary(df_providers, df_members)
                response = ask_agent(prompt, summary, st.session_state.ai_chat_history)
                st.markdown(response)
        st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
