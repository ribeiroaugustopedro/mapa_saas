import pandas as pd
import streamlit as st
import os
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def generate_data_summary(df_prestadores, df_carteira, simulation_results=None, benchmark_sim=None, raio_km=5, map_modes=[]):
    summary = []
    
    summary.append(f"### CONFIGURAÇÕES DE ANÁLISE")
    summary.append(f"- **Raio de Abrangência Selecionado**: {raio_km} km")
    summary.append(f"- **Camadas Ativas no Mapa**: {', '.join(map_modes) if map_modes else 'Apenas Marcadores'}")
    
    n_prest = len(df_prestadores)
    n_carteira = df_carteira['id_usuario'].nunique() if 'id_usuario' in df_carteira.columns else len(df_carteira)
    
    summary.append(f"### VISÃO GERAL")
    summary.append(f"- **Total de Prestadores Visíveis**: {n_prest}")
    summary.append(f"- **Base de Carteira Totais**: {n_carteira}")

    if simulation_results:
        lat_opt, lon_opt, count_opt = simulation_results
        summary.append(f"### SIMULAÇÃO (ATINGIR META)")
        summary.append(f"- **Novo Ponto Sugerido**: Coordenadas ({lat_opt:.4f}, {lon_opt:.4f})")
        summary.append(f"- **Potencial de Captação**: {count_opt:,} clientes no raio de {raio_km}km")
        
        if benchmark_sim:
            lat_e, lon_e, count_e, nome_e = benchmark_sim
            diff = count_opt - count_e
            perc = (count_opt / count_e - 1) * 100 if count_e > 0 else 0
            summary.append(f"- **Comparativo com Melhor Atual ({nome_e})**: {'Melhoria' if diff > 0 else 'Diferença'} de **{diff:,}** ({perc:+.1f}%)")
    
    summary.append(f"### GEOGRAFIA")
    
    if 'regiao' in df_prestadores.columns:
        top_reg_prest = df_prestadores['regiao'].value_counts().head(5).to_dict()
        summary.append(f"- **Top 5 Regiões (Rede)**: {top_reg_prest}")
        
    if 'tipo_prestador' in df_prestadores.columns:
        tipos = df_prestadores['tipo_prestador'].value_counts().to_dict()
        summary.append(f"- **Perfil da Rede (Tipos)**: {tipos}")
        
    summary.append(f"### PERFIL DOS CLIENTES")
    if 'faixa_etaria' in df_carteira.columns:
        age_dist = df_carteira['faixa_etaria'].value_counts().head(5).to_dict()
        summary.append(f"- **Distribuição por Faixa Etária**: {age_dist}")
    
    if 'produto' in df_carteira.columns:
        prod_dist = df_carteira['produto'].value_counts().head(5).to_dict()
        summary.append(f"- **Principais Produtos Utilizados**: {prod_dist}")

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
    
    if not api_key or api_key == "INSIRA_SUA_API_KEY_AQUI":
        return "Configuração Requerida: Chave de API não detectada. Por favor, valide as credenciais no ambiente de produção ou no arquivo de configurações locais."
        
    full_prompt = f"""
    Você é o Chief Intelligence Officer (CIO) e Diretor de Estratégia de Rede da Leve Saúde.
    Seu tom deve ser altamente profissional, sênior, executivo e analítico.
    Você atua como um parceiro estratégico para a diretoria, fornecendo insights precisos e recomendações baseadas exclusivamente em dados.

    NORMAS DE COMUNICAÇÃO (CRÍTICO):
    1.  **Sem Emoticons**: É estritamente proibido o uso de qualquer tipo de emoticon ou emoji em suas respostas.
    2.  **Profissionalismo**: Mantenha uma linguagem corporativa polida e assertiva.
    3.  **Objetividade**: Se o usuário apenas te cumprimentar, responda de forma executiva e cordial.
    4.  **Estrutura Executiva**: 
        - Para análises estratégicas, utilize os títulos: **Diagnóstico Situacional**, **Insights Críticos** e **Recomendações Estratégicas**.
        - Para dúvidas pontuais, seja direto e formal.

    BASE DE DADOS PARA ANÁLISE:
    {context_summary}
    
    HISTÓRICO DA CONVERSA:
    {history[-5:] if history else "Sem histórico relevante."}
    
    CONSULTA DO EXECUTIVO:
    {user_question}
    
    RESTRIÇÕES ADICIONAIS:
    - Nunca invente dados. Seja preciso e cite os valores do contexto sempre que possível.
    - Use **negrito** apenas para destacar métricas e termos técnicos fundamentais.
    """

    def is_retryable_exception(e):
        return "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def call_gemini():
        client = genai.Client(api_key=api_key)
        return client.models.generate_content(
            model='gemini-1.5-flash',
            contents=full_prompt
        )

    try:
        response = call_gemini()
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return "Limite de cota atingido (429 RESOURCE_EXHAUSTED)."
        return f"Erro ao consultar Gemini (google.genai): {error_msg}"
