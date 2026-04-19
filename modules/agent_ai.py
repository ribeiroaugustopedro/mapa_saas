import pandas as pd
import streamlit as st
import os
import time
from google import genai
from groq import Groq # Fallback provider
import warnings

# Suppress the legacy FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning)

def ask_agent(user_question, context_summary, history=[], provider_choice="Auto"):
    # --- GEMINI CONFIG ---
    gemini_keys = []
    pk = st.secrets.get("gemini", {}).get("api_key") or os.getenv("GEMINI_API_KEY")
    if pk: gemini_keys.append(pk)
    for i in range(1, 5):
        key = st.secrets.get("gemini", {}).get(f"api_key_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
        if key: gemini_keys.append(key)

    # --- GROQ CONFIG ---
    groq_keys = []
    gk = st.secrets.get("groq", {}).get("api_key") or os.getenv("GROQ_API_KEY")
    if gk: groq_keys.append(gk)
    for i in range(1, 3):
        key = st.secrets.get("groq", {}).get(f"api_key_{i}") or os.getenv(f"GROQ_API_KEY_{i}")
        if key: groq_keys.append(key)

    last_err_msg = ""
    
    # Construct history string
    history_context = ""
    if history:
        history_context = "Conversation History:\n" + "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-5:]]) + "\n\n"

    prompt_full = f"{history_context}Context: {context_summary}\n\nQuestion: {user_question}"

    # PHASE 1: GEMINI
    if provider_choice in ["Auto", "Gemini"]:
        priority_gemini_models = ["gemini-2.0-flash"]
        for api_key in gemini_keys:
            try:
                client = genai.Client(api_key=api_key)
                for model_name in priority_gemini_models:
                    try:
                        # New SDK (google-genai) does NOT use 'models/' prefix
                        response = client.models.generate_content(model=model_name, contents=prompt_full)
                        if response.text:
                            st.session_state["active_model"] = model_name.replace("-", " ").title()
                            return response.text
                    except Exception as e:
                        last_err_msg = f"Gemini Error ({model_name}): {str(e)}"
                        if any(x in last_err_msg.upper() for x in ["429", "QUOTA", "LIMIT", "TOO MANY REQUESTS"]):
                            continue 
                        break
            except Exception as e:
                last_err_msg = f"Gemini Init Error: {str(e)}"
                continue

    # PHASE 2: GROQ
    if provider_choice in ["Auto", "Groq"]:
        priority_groq_models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "llama3-8b-8192"]
        for api_key in groq_keys:
            try:
                client = Groq(api_key=api_key)
                for model_name in priority_groq_models:
                    try:
                        messages = [{"role": "system", "content": f"You are a Network Planning Assistant. Context: {context_summary}"}]
                        for msg in history[-5:]: messages.append({"role": msg["role"], "content": msg["content"]})
                        messages.append({"role": "user", "content": user_question})

                        chat_completion = client.chat.completions.create(messages=messages, model=model_name)
                        if chat_completion.choices[0].message.content:
                            st.session_state["active_model"] = f"Groq {model_name.split('-')[0].title()}"
                            return chat_completion.choices[0].message.content
                    except Exception as e:
                        last_err_msg = f"Groq Error ({model_name}): {str(e)}"
                        if "429" in last_err_msg: continue
                        break
            except: continue

    if not gemini_keys and not groq_keys:
        return "Configuration Error: No API keys found."

    return f"Intelligence Service at capacity. (Last error: {last_err_msg[:100]})"

def generate_data_summary(df_providers, df_members):
    return f"Network State: {len(df_providers)} Providers. Active Users: {len(df_members):,} users."

def render_ai_advisor(df_members, df_providers):
    # Initialize State
    if "ai_chat_history" not in st.session_state: st.session_state.ai_chat_history = []
    if "active_model" not in st.session_state: st.session_state["active_model"] = "Gemini 2.0 Flash"
    if "ai_provider" not in st.session_state: st.session_state["ai_provider"] = "Auto"
    
    # CSS for a premium AI Terminal feel with Rainbow Accent
    st.markdown("""
        <style>
        .ai-terminal-container {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 20px;
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
        /* Minimalist Buttons */
        .stButton > button {
            font-size: 0.75rem !important;
            padding: 4px 12px !important;
            min-height: 0px !important;
        }
        /* Styling the Chat Input area to match header */
        .stChatInput {
            padding: 0 !important;
        }
        .stChatInput > div {
            width: 92% !important;
            margin: 0 auto !important;
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
        /* Minify Font in Segmented Control */
        div[data-testid="stSegmentedControl"] button p {
            font-size: 0.65rem !important;
            font-weight: 600 !important;
        }
        /* Spacing for messages so they don't hide behind input */
        .chat-scroll-area {
            margin-bottom: 20px;
            margin-top: 10px;
        }
        </style>
        <div class="ai-terminal-container">
            <div class="ai-terminal-header">
                <div class="ai-title" style="text-align: center;">Network Intelligence</div>
                <div class="rainbow-line"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Provider Selection
    st.markdown('<div class="quick-action-label">Engine Control</div>', unsafe_allow_html=True)
    st.segmented_control(
        "Intelligence Provider", 
        options=["Auto", "Gemini", "Groq"], 
        key="ai_provider",
        label_visibility="collapsed"
    )

    # Structural Demarcation
    st.markdown('<div class="quick-action-label">Analysis Presets</div>', unsafe_allow_html=True)
    
    # Dynamic Suggestions
    suggestions = [
        "Identify geographical gaps in provider coverage.",
        "Analyze user-to-provider density by region.",
        "Suggest 3 strategic locations for new network hubs.",
        "List providers with less than 50% coverage efficiency.",
        "Identify regions with high user demand but low provider count."
    ]
    if "suggestion_idx" not in st.session_state: st.session_state.suggestion_idx = 0
    
    auto_prompt = None
    col_btn, _ = st.columns([1, 1])
    with col_btn:
        if st.button("Suggestion", use_container_width=True):
            auto_prompt = suggestions[st.session_state.suggestion_idx]
            st.session_state.suggestion_idx = (st.session_state.suggestion_idx + 1) % len(suggestions)
        
        if st.button("Clear Cache", use_container_width=True):
            st.session_state.ai_chat_history = []
            st.rerun()

    # Chat history area
    st.markdown('<div class="chat-scroll-area">', unsafe_allow_html=True)
    for chat in st.session_state.ai_chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; line-height: 1.5; color: #f8fafc;">{chat["content"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Process prompt
    prompt = st.chat_input("Analysis Request...") or auto_prompt
    
    if prompt:
        with st.chat_message("user"):
            st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; color: #ffffff; font-weight: 600;">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.ai_chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                summary = generate_data_summary(df_providers, df_members)
                response = ask_agent(prompt, summary, st.session_state.ai_chat_history, provider_choice=st.session_state["ai_provider"])
                st.markdown(f'<div style="font-family: \'Inter\', sans-serif; font-size: 0.9rem; line-height: 1.5; color: #f8fafc;">{response}</div>', unsafe_allow_html=True)
        st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
        if auto_prompt: st.rerun()
