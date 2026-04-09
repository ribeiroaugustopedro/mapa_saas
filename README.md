# GeoMap SaaS - Geospatial Network Intelligence

A robust **Location Intelligence** platform designed for strategic healthcare network management. GeoMap integrates member data analysis, provider mapping, and geospatial optimization algorithms into a modern, minimalist interface inspired by a high-end professional portfolio.

---

## 🎨 Visual Identity & UX
GeoMap was developed with a focus on a premium **User Experience (UX)**:
- **Native Dark Mode**: Interface optimized for readability and modern aesthetics.
- **Glassmorphism**: Components featuring transparency and background blur.
- **Rainbow Micro-Animations**: Rainbow gradient effects on Call-to-Action (CTA) buttons and toggles, ensuring a vibrant and interactive interface.

## 🛠️ Core Features
- **Dynamic Exploration**: Intelligent filters that maintain map state without resetting the view.
- **Additive Search**: Search for provider names that are added to the filtered view.
- **Optimal Point Simulation ("Goal Seeking")**: Algorithm that identifies the best location for network expansion based on member density.
- **AI Assistant (GenAI)**: Integration with **Google Gemini 1.5 Pro/Flash** for scenario analysis and strategic consulting in natural language.
- **Density Heatmaps**: Clear visualization of customer concentration vs. network coverage.

## 🚀 How to Run (Local)
1. Ensure you have Python 3.10+ installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   streamlit run app.py
   ```

## 📦 Data Architecture
The project utilizes a modular data pipeline:
- **Source**: Data ingestion via local DuckDB (Gold layer).
- **Backend**: Python + Streamlit.
- **Map**: Folium with Leaflet.js extensions.
- **Intelligence**: Google Generative AI (Gemini SDK).

---
> [!TIP]
> To host on **Streamlit Cloud**, ensure you configure the Gemini API Key in `.streamlit/secrets.toml`.
