import pandas as pd
import streamlit as st
import os
import time
from google import genai
import warnings

# Suppress the legacy FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning)

def ask_agent(user_question, context_summary, history=[]):
    # Support for multiple keys to rotate and avoid quotas
    api_keys = []
    # Primary key
    pk = st.secrets.get("gemini", {}).get("api_key") or os.getenv("GEMINI_API_KEY")
    if pk: api_keys.append(pk)
    
    # Discovery of additional keys (GEMINI_API_KEY_1, _2, etc)
    for i in range(1, 5):
        key = st.secrets.get("gemini", {}).get(f"api_key_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
        if key: api_keys.append(key)
        
    if not api_keys: return "API Configuration Missing. Please provide a GEMINI_API_KEY."
    
    priority_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    last_err_msg = ""
    
    # Double rotation: Keys then Models
    for api_key in api_keys:
        try:
            client = genai.Client(api_key=api_key)
            for model_name in priority_models:
                try:
                    # Defensive: handle potential naming prefix differences
                    m_id = model_name if "models/" in model_name else f"models/{model_name}"
                    response = client.models.generate_content(
                        model=m_id,
                        contents=f"Context: {context_summary}\n\nQuestion: {user_question}"
                    )
                    if response.text:
                        st.session_state["active_model"] = model_name.replace("-", " ").title()
                        return response.text
                except Exception as e:
                    last_err_msg = str(e)
                    if "404" in last_err_msg: continue # Try next model
                    if any(x in last_err_msg.upper() for x in ["429", "503", "QUOTA", "LIMIT"]):
                        continue
                    break # Critical error for this key
        except: continue
                    
    return f"Strategic Advisory at capacity. (Last error: {last_err_msg[:100]})"

def generate_data_summary(df_providers, df_members):
    return f"Network State: {len(df_providers)} Providers. Active Users: {len(df_members):,} users."

def render_ai_advisor(df_members, df_providers):
    # Initialize State at the very beginning to avoid KeyErrors
    if "ai_chat_history" not in st.session_state: st.session_state.ai_chat_history = []
    if "active_model" not in st.session_state: st.session_state["active_model"] = "Gemini 2.0 Flash"
    
    # CSS for a premium AI Terminal feel with Rainbow Accent
    st.markdown("""
        <style>
        .ai-terminal-container {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 25px;
            background: #ffffff;
        }
        .ai-terminal-header {
            background: #0f172a;
            padding: 1.25rem;
            position: relative;
        }
        .rainbow-line {
            height: 3px;
            width: 100%;
            background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981, #3b82f6, #6366f1, #8b5cf6);
            position: absolute;
            bottom: 0;
            left: 0;
        }
        .ai-title {
            color: #f8fafc;
            font-size: 0.85rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 0;
        }
        .ai-subtitle {
            color: #64748b;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-top: 4px;
        }
        .quick-action-label {
            font-size: 0.65rem;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            margin-bottom: 8px;
            margin-top: 25px;
        }
        /* Styling the Chat Input area to match header */
        .stChatInput {
            padding: 0 !important;
        }
        .stChatInput > div {
            border: 1px solid #475569 !important;
            border-radius: 12px !important;
            background: #0f172a !important;
            padding: 8px 12px !important;
        }
        .stChatInput textarea {
            color: #f8fafc !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 1rem !important;
            line-height: 1.5 !important;
        }
        /* Centering the Send Button icon */
        .stChatInput button {
            display: flex !important;
            align-items: center !important;
            margin-top: auto !important;
            margin-bottom: auto !important;
        }
        /* Spacing for messages so they don't hide behind input */
        .chat-scroll-area {
            margin-bottom: 20px;
            margin-top: 10px;
        }
        </style>
        <div class="ai-terminal-container">
            <div class="ai-terminal-header">
                <div class="ai-title">Network Intelligence</div>
                <div class="ai-subtitle">""" + st.session_state["active_model"].upper() + """ Analysis</div>
                <div class="rainbow-line"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Structural Demarcation
    st.markdown('<hr style="margin: 20px 0 10px 0; border: none; border-top: 1px solid #334155; opacity: 0.5;">', unsafe_allow_html=True)
    st.markdown('<div class="quick-action-label">Quick Actions</div>', unsafe_allow_html=True)
    
    auto_prompt = None
    
    # Vertically stacked buttons for better fit in sidebar
    if st.button("Analyze Gaps", use_container_width=True):
        auto_prompt = "Identify the major geographical gaps in the current provider coverage."
    if st.button("Optimize Density", use_container_width=True):
        auto_prompt = "Analyze the user-to-provider density and identify underserved regions."
    if st.button("Clear History", use_container_width=True):
        st.session_state.ai_chat_history = []
        st.rerun()

    # Secondary demarcation
    st.markdown('<hr style="margin: 15px 0 10px 0; border: none; border-top: 1px solid #334155; opacity: 0.5;">', unsafe_allow_html=True)

    # Chat history pushed flush to controls
    st.markdown('<div class="chat-scroll-area">', unsafe_allow_html=True)
    for chat in st.session_state.ai_chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; line-height: 1.5; color: #f8fafc;">{chat["content"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Process prompt (either from button or chat_input)
    prompt = st.chat_input("Analysis Request...") or auto_prompt
    
    if prompt:
        with st.chat_message("user"):
            st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; color: #ffffff; font-weight: 600;">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.ai_chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Processing Topology..."):
                summary = generate_data_summary(df_providers, df_members)
                response = ask_agent(prompt, summary, st.session_state.ai_chat_history)
                st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; line-height: 1.5; color: #f8fafc;">{response}</div>', unsafe_allow_html=True)
        st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
        if auto_prompt: st.rerun() # Ensure buttons clear correctly
