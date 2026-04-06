# GeoMap SaaS - Inteligência Geográfica de Rede

Uma plataforma robusta de **Location Intelligence** projetada para gestão estratégica de redes de saúde. O GeoMap integra análise de dados de beneficiários, mapeamento de prestadores e algoritmos de otimização geográfica em uma interface moderna e minimalista inspirada no portfólio profissional.

---

## 🎨 Identidade Visual & UX
O GeoMap foi desenvolvido com foco em **User Experience (UX)** premium:
- **Dark Mode Nativo**: Interface otimizada para legibilidade e estética moderna.
- **Glassmorphism**: Componentes com transparência e desfoque de fundo.
- **Micro-Animações Rainbow**: Efeitos de gradiente arco-íris em botões de ação (CTAs) e toggles, garantindo uma interface viva e interativa.

## 🛠️ Core Features
- **Exploração Dinâmica**: Filtros inteligentes que não resetam a visão do mapa.
- **Busca Aditiva**: Pesquisa por nomes de prestadores que se somam à visão filtrada.
- **Simulação de Ponto Ótimo ("Atingir Meta")**: Algoritmo que identifica a melhor localização para expansão de rede com base na densidade de carteira.
- **Assistente IA (GenAI)**: Integração com **Google Gemini 2.0 Flash** para análise de cenários e consultoria estratégica em linguagem natural.
- **Heatmaps de Densidade**: Visualização clara de concentração de clientes vs. cobertura de rede.

## 🚀 Como Executar (Local)
1. Certifique-se de ter Python 3.10+ instalado.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Rode a aplicação:
   ```bash
   streamlit run app.py
   ```

## 📦 Arquitetura de Dados
O projeto utiliza um pipeline de dados modular:
- **Origem**: Ingestão de dados via DuckDB local (camada Gold).
- **Backend**: Python + Streamlit.
- **Mapa**: Folium com extensões de Leaflet.js.
- **Inteligência**: Google Generative AI (Gemini SDK).

---
> [!TIP]
> Para hospedar no **Streamlit Cloud**, certifique-se de configurar a API Key do Gemini em `.streamlit/secrets.toml`.
