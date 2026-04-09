import pandas as pd
import numpy as np
import streamlit as st
import os
import tempfile
import time
import io

def haversine_vectorized(lat1, lon1, lat2_array, lon2_array):
    R = 6371
    phi1, phi2 = np.radians(lat1), np.radians(lat2_array)
    dphi = np.radians(lat2_array - lat1)
    dlambda = np.radians(lon2_array - lon1)
    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

def find_optimal_point(df_target, radius_km, df_providers=None, count_unique=True, max_candidates=1000, grid_size_fine=25):
    if df_target.empty or 'loc_latitude' not in df_target.columns or 'loc_longitude' not in df_target.columns:
        return None, None
    coords = df_target.dropna(subset=['loc_latitude', 'loc_longitude'])
    if coords.empty:
        return None, None
    lat_data = coords['loc_latitude'].values
    lon_data = coords['loc_longitude'].values
    ids_data = coords['user_id'].values if 'user_id' in coords.columns and count_unique else None
    best_existing = None
    max_e = -1
    if df_providers is not None and not df_providers.empty:
        for _, row in df_providers.iterrows():
            if pd.isna(row['loc_latitude']) or pd.isna(row['loc_longitude']): continue
            dist = haversine_vectorized(row['loc_latitude'], row['loc_longitude'], lat_data, lon_data)
            mask = dist <= radius_km
            if count_unique and ids_data is not None:
                count = len(np.unique(ids_data[mask]))
            else:
                count = np.sum(mask)
            if count > max_e:
                max_e = count
                best_existing = (row['loc_latitude'], row['loc_longitude'], count, row.get('prov_name', 'Provider'))
    if len(coords) > max_candidates:
        sampled_coords = coords.sample(n=max_candidates, random_state=42)
    else:
        sampled_coords = coords
    candidatos_lat = sampled_coords['loc_latitude'].values
    candidatos_lon = sampled_coords['loc_longitude'].values
    if df_providers is not None and not df_providers.empty:
        p_coords = df_providers.dropna(subset=['loc_latitude', 'loc_longitude'])
        candidatos_lat = np.concatenate([candidatos_lat, p_coords['loc_latitude'].values])
        candidatos_lon = np.concatenate([candidatos_lon, p_coords['loc_longitude'].values])
    best_global_new = None
    max_global_new = -1
    for i in range(len(candidatos_lat)):
        lt, ln = candidatos_lat[i], candidatos_lon[i]
        dist = haversine_vectorized(lt, ln, lat_data, lon_data)
        mask = dist <= radius_km
        if count_unique and ids_data is not None:
            count = len(np.unique(ids_data[mask]))
        else:
            count = np.sum(mask)
        if count > max_global_new:
            max_global_new = count
            best_global_new = (lt, ln)
    if not best_global_new:
        return None, best_existing
    delta_lat = 0.005
    delta_lon = 0.005
    lats_f = np.linspace(best_global_new[0] - delta_lat, best_global_new[0] + delta_lat, grid_size_fine)
    lons_f = np.linspace(best_global_new[1] - delta_lon, best_global_new[1] + delta_lon, grid_size_fine)
    best_final_new = best_global_new
    max_final_new = max_global_new
    for lat_f in lats_f:
        for lon_f in lons_f:
            dist = haversine_vectorized(lat_f, lon_f, lat_data, lon_data)
            mask = dist <= radius_km
            if count_unique and ids_data is not None:
                count = len(np.unique(ids_data[mask]))
            else:
                count = np.sum(mask)
            if count > max_final_new:
                max_final_new = count
                best_final_new = (lat_f, lon_f)
    return (best_final_new[0], best_final_new[1], max_final_new), best_existing

def generate_filters(df, container, config_filters, key_prefix="filter"):
    df_filtered = df.copy()
    if not config_filters:
        return df_filtered
    for config in config_filters:
        col = config.get("col")
        if col not in df.columns:
            continue
        label = config.get("label", col.replace("_", " ").title())
        multivalue = config.get("multivalue", False)
        separator = config.get("separator", "|")
        if multivalue:
            s_list = (
                df_filtered[col]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.split(separator)
                .apply(lambda xs: {x.strip() for x in xs if x and x.strip()})
            )
            options = sorted(set().union(*s_list.tolist())) if len(s_list) else []
        else:
            options = sorted(df_filtered[col].dropna().astype(str).unique())
        key = f"{key_prefix}_{col}"
        selected_items = container.multiselect(label, options, key=key)
        if selected_items:
            if multivalue:
                selected_set = {x.upper().strip() for x in selected_items}
                mask = s_list.apply(lambda s: bool(s.intersection(selected_set)))
                df_filtered = df_filtered[mask]
            else:
                df_filtered = df_filtered[df_filtered[col].astype(str).isin(selected_items)]
    return df_filtered

def detect_filter_columns(df, ignored_columns=None, multivalue_separator="|"):
    if ignored_columns is None:
        ignored_columns = []
    generated_config = []
    ignored_set = {c.lower() for c in ignored_columns}
    ORDER_WEIGHTS = {
        "region": 10, "state": 20, "city": 30, "neighborhood": 40, "zip_code": 50,
        "type": 60, "modality": 70, "product": 80, "age_group": 90,
        "status": 100
    }
    candidates = []
    for col in df.columns:
        if col.lower() in ignored_set: continue
        if df[col].isnull().all(): continue
        dtype_str = str(df[col].dtype).lower()
        is_numeric = any(t in dtype_str for t in ["int", "float", "double", "decimal"])
        if is_numeric and df[col].nunique() > 20: continue
        sample_data = df[col].dropna().astype(str)
        if sample_data.empty: continue
        has_separator = sample_data.head(100).str.contains(multivalue_separator, regex=False).any()
        label_base = col.replace("user_", "").replace("loc_", "").replace("contract_", "").replace("prov_", "").replace("_", " ").title()
        clean_col = col.lower().replace("loc_", "").replace("contract_", "").replace("user_", "").replace("prov_", "")
        weight = 999
        for key, w in ORDER_WEIGHTS.items():
            if key in clean_col:
                weight = w
                break
        candidates.append({"col": col, "label": label_base, "multivalue": bool(has_separator), "separator": multivalue_separator, "weight": weight})
    candidates.sort(key=lambda x: (x["weight"], x["label"]))
    return candidates

def capture_map_to_bytes(mapa):
    tmp_html = os.path.join(tempfile.gettempdir(), f"map_{int(time.time())}.html")
    try:
        mapa.save(tmp_html)
        import asyncio
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1600, 'height': 800})
            abs_path = os.path.abspath(tmp_html).replace('\\', '/')
            file_url = f"file:///{abs_path}"
            page.goto(file_url, wait_until="networkidle")
            time.sleep(1)
            img_bytes = page.screenshot(full_page=True)
            browser.close()
            return img_bytes
    except:
        return None
    finally:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)