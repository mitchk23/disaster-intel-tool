import streamlit as st
import pandas as pd
import json
import pydeck as pdk
from datetime import datetime, timezone
from data_sources import fetch_usgs_quakes, fetch_gdacs_events, fetch_nasa_firms
from utils import geocode, haversine_km

st.set_page_config(page_title="HADRI – Disaster Intelligence", layout="wide")
st.title("HADRI – Disaster Intelligence (Starter App)")

with st.expander("About this tool"):
    st.markdown("""
    This lightweight app pulls near-real-time hazard feeds (earthquakes, GDACS all-hazards, and NASA FIRMS fires),
    lets you filter by Area of Interest (AOI), and export/share a quick situational snapshot.

    **Why this approach?**
    - Runs locally or on Streamlit Cloud.
    - Safe by design: you decide what sources & outputs to include.
    - Easy to extend with scoring, exposure, and Make.com webhooks.
    """)

# --- Controls
col1, col2, col3 = st.columns([1,1,1])
with col1:
    hours_back = st.slider("Look-back window (hours)", 6, 168, 24)
with col2:
    aoi_query = st.text_input("AOI (place name/address to geocode)", value="Chiang Mai, Thailand")
with col3:
    radius_km = st.number_input("AOI radius (km)", min_value=10, max_value=1000, value=410, step=10)

# --- Fetch data
with st.spinner("Fetching hazard feeds…"):
    try:
        quakes = fetch_usgs_quakes(hours_back=hours_back)
    except Exception as e:
        st.warning(f"USGS fetch failed: {e}")
        quakes = pd.DataFrame()

    try:
        gdacs = fetch_gdacs_events(hours_back=hours_back)
    except Exception as e:
        st.warning(f"GDACS fetch failed: {e}")
        gdacs = pd.DataFrame()

    try:
        fires = fetch_nasa_firms(hours_back=hours_back)
    except Exception as e:
        st.warning(f"NASA FIRMS fetch failed: {e}")
        fires = pd.DataFrame()

st.subheader("Live Feeds")
tabs = st.tabs(["Earthquakes (USGS)", "All-hazards (GDACS)", "Fires (NASA FIRMS)"])
with tabs[0]:
    st.dataframe(quakes, use_container_width=True)
with tabs[1]:
    st.dataframe(gdacs, use_container_width=True)
with tabs[2]:
    st.dataframe(fires, use_container_width=True)

# --- AOI Filter
st.subheader("Area of Interest filter")
aoi_lat, aoi_lon = None, None
if aoi_query:
    try:
        aoi_lat, aoi_lon = geocode(aoi_query)
        st.success(f"AOI: {aoi_query} → {aoi_lat:.4f}, {aoi_lon:.4f}")
    except Exception as e:
        st.error(f"Geocoding failed: {e}")

def filter_by_aoi(df, lat_col, lon_col, label):
    if df is None or df.empty or aoi_lat is None or aoi_lon is None:
        st.markdown(f"**{label}: 0 within {radius_km} km**")
        return pd.DataFrame()

    # Clean coords
    f = df.copy()
    f = f.dropna(subset=[lat_col, lon_col])
    f[lat_col] = pd.to_numeric(f[lat_col], errors="coerce")
    f[lon_col] = pd.to_numeric(f[lon_col], errors="coerce")
    f = f.dropna(subset=[lat_col, lon_col])

    if f.empty:
        st.markdown(f"**{label}: 0 within {radius_km} km**")
        return pd.DataFrame()

    f["distance_km"] = f.apply(lambda r: haversine_km(aoi_lat, aoi_lon, r[lat_col], r[lon_col]), axis=1)
    f = f[f["distance_km"] <= radius_km].sort_values("distance_km")

    st.markdown(f"**{label}: {len(f)} within {radius_km} km**")
    st.dataframe(f, use_container_width=True)
    return f

colA, colB, colC = st.columns(3)
with colA:
    f_quakes = filter_by_aoi(quakes, "latitude", "longitude", "Quakes")
with colB:
    f_gdacs = filter_by_aoi(gdacs, "latitude", "longitude", "GDACS")
with colC:
    f_fires = filter_by_aoi(fires, "latitude", "longitude", "Fires")
# --- Map view (AOI + events)
if aoi_lat is not None and aoi_lon is not None:
    # Combine points we actually have coordinates for
    def pick(df, lat, lon, label):
        if isinstance(df, pd.DataFrame) and not df.empty:
            d = df[[lat, lon]].copy()
            d.columns = ["lat", "lon"]
            d["label"] = label
            return d
        return pd.DataFrame(columns=["lat","lon","label"])

    points = pd.concat([
        pick(f_quakes, "latitude", "longitude", "Quake"),
        pick(f_fires,  "latitude", "longitude", "Fire"),
        pick(f_gdacs,  "latitude", "longitude", "GDACS"),
    ], ignore_index=True)

    # layers: AOI ring + points
    layers = []

    # AOI ring (approx by 60 points on a circle)
    import math
    ring = []
    R = 6371.0
    rad = radius_km / R
    for i in range(60):
        bearing = math.radians(i*6)
        lat1 = math.radians(aoi_lat); lon1 = math.radians(aoi_lon)
        lat2 = math.asin(math.sin(lat1)*math.cos(rad) + math.cos(lat1)*math.sin(rad)*math.cos(bearing))
        lon2 = lon1 + math.atan2(math.sin(bearing)*math.sin(rad)*math.cos(lat1),
                                 math.cos(rad)-math.sin(lat1)*math.sin(lat2))
        ring.append([math.degrees(lon2), math.degrees(lat2)])

    layers.append(pdk.Layer(
        "PolygonLayer",
        data=[{"polygon": ring}],
        get_polygon="polygon",
        stroked=True,
        filled=False,
        get_line_width=2,
    ))

    if not points.empty:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=points,
            get_position='[lon, lat]',
            get_radius=4000,  # 4 km marker size
            pickable=True,
        ))

    view = pdk.ViewState(latitude=aoi_lat, longitude=aoi_lon, zoom=6)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{label}"}))

# --- Quick snapshot / export
st.subheader("Quick Snapshot")
summary = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "hours_back": hours_back,
    "aoi": {"query": aoi_query, "lat": aoi_lat, "lon": aoi_lon, "radius_km": radius_km},
    "counts": {
        "usgs_total": len(quakes),
        "gdacs_total": len(gdacs),
        "fires_total": len(fires),
        "usgs_in_aoi": len(f_quakes) if isinstance(f_quakes, pd.DataFrame) else 0,
        "gdacs_in_aoi": len(f_gdacs) if isinstance(f_gdacs, pd.DataFrame) else 0,
        "fires_in_aoi": len(f_fires) if isinstance(f_fires, pd.DataFrame) else 0,
    },
}
st.code(json.dumps(summary, indent=2))
