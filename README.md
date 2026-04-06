# Pedro Augusto Ribeiro - Data & Software Ecosystem

Este repositório serve como a raiz do meu ecossistema de projetos, integrando engenharia de dados, inteligência artificial e interfaces web de alta performance.

---

## 🏛️ Arquitetura do Hub (Medallion)

O ecossistema é dividido em três pilares principais, cada um com seu próprio ciclo de vida e repositório:

### 1. [Analytics Warehouse](warehouse/) (The Backbone)
- **O que faz**: Ingestão, modelagem e anonimização de dados brutos.
- **Tecnologias**: DuckDB, dbt, Python, SQL.
- **Output**: Alimenta todos os dashboards e aplicações de negócio via camada *Gold*.

### 2. [GeoMap SaaS](mapa_estabelecimentos/) (The Application)
- **O que faz**: Ferramenta de *Location Intelligence* para redes de saúde com consultoria via IA integrada.
- **Tecnologias**: Streamlit, Folium, Google Gemini AI.
- **Deploy**: Pronto para **Streamlit Cloud**.

### 3. [Site Portfolio](site_portfolio/) (The Showcase)
- **O que faz**: Meu portfólio profissional e hub de projetos ao vivo.
- **Tecnologias**: Vite, React, Three.js.
- **Deploy**: Hospedado em **paribeiro.com** via GitHub Pages.

---

## 🗺️ Roadmap de Integrações Futuras

- [ ] **SQL on Web**: Implementar DuckDB-WASM no portfólio para consultas SQL interativas pelo usuário final.
- [ ] **API de Dados**: Migrar o warehouse para uma API unificada que sirva múltiplos front-ends.
- [ ] **Novos Dashboards**: Projetos de análise financeira e logística integrados ao core do warehouse.

---

## 🛠️ Como Iniciar
Cada projeto possui seu próprio ambiente isolado (`.venv`). Para rodar qualquer um:
1. Navegue até a pasta do projeto.
2. Crie ou ative a `.venv` local.
3. Instale as dependências via `pip install -r requirements.txt` ou `npm install`.

---
> [!NOTE]
> Este workspace reflete um compromisso com a escalabilidade, segurança de dados e excelência técnica em todas as camadas da aplicação.
