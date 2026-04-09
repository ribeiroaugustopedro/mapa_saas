# Network Planner - Geospatial Network Intelligence

A professional location intelligence platform designed for strategic network management. It integrates member density analysis, provider coverage mapping, and geospatial optimization algorithms into a minimalist, high-performance interface.

## Core Features
- **Dynamic Spatial Exploration**: Interactive filters that maintain map state during analysis.
- **Provider Network Mapping**: Visualization of healthcare clusters with custom iconography and coverage radii.
- **Optimal Point Simulation**: Algorithm-driven identification of strategic locations for network expansion based on portfolio density.
- **AI Strategic Advisory**: Integration with Google Gemini for natural language data analysis and strategic insights.
- **Density Analytics**: Heatmap visualizations reflecting customer concentration versus existing network infrastructure.

## Tech Stack
- **Frontend**: Streamlit
- **Geospatial Engine**: Folium (Leaflet.js)
- **Data Engine**: DuckDB
- **Artificial Intelligence**: Google Generative AI (Gemini Flash)
- **Visualization**: Altair

## Local Installation
1. Clone the repository and navigate to the project directory.
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the application:
   ```bash
   streamlit run app.py
   ```

## Configuration
For full AI functionality, ensure you have a Google Gemini API Key configured in `.streamlit/secrets.toml` or as an environment variable.
