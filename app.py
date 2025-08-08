
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from data_sources import fetch_usgs_quakes, fetch_gdacs_events, fetch_nasa_firms
from utils import geocode, haversine_km

st.set_page_config(page_title="HADRI – Disaster Intelligence", layout="wide")

st.title("HADRI – Disaster Intelligence (Starter App)")

with st.expander("About this tool"):
    st.markdown("""
    This lightweight app pulls near‑real‑time hazard feeds (earthquakes, GDACS all-hazards, and NASA FIRMS fires),
    lets you filter by Area of Interest (AOI), and export/share a quick situational snapshot.
    
    **Why this approach?**
    - Runs locally (or on a tiny cloud box) with Streamlit.
    - Safe by design: you decide what sources & outputs to include.
    - Easy to extend with more feeds, scoring, and Make.com webhooks.
    """)

# --- Controls
col1, col2, col3 = st.columns([1,1,1])
with col1:
    hours_back = st.slider("Look-back window (hours)", 6, 168, 24)
with col2:
    aoi_query = st.text_input("AOI (place name/address to geocode)", value="Chiang Mai, Thailand")
with col3:
    radius_km = st.number_input("AOI radius (km)", min_value=10, max_value=1000, value=250, step=10)

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
    if df.empty or aoi_lat is None:
        return pd.DataFrame()
    df = df.copy()
    df["distance_km"] = df.apply(lambda r: haversine_km(aoi_lat, aoi_lon, r[lat_col], r[lon_col]), axis=1)
    f = df[df["distance_km"] <= radius_km].sort_values("distance_km")
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
        "usgs_in_aoi": len(f_quakes) if not isinstance(f_quakes, int) else 0,
        "gdacs_in_aoi": len(f_gdacs) if not isinstance(f_gdacs, int) else 0,
        "fires_in_aoi": len(f_fires) if not isinstance(f_fires, int) else 0,
    },
}

st.code(json.dumps(summary, indent=2))

csv_zip = io.BytesIO()
with zipfile.ZipFile(csv_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    if not quakes.empty: zf.writestr("quakes.csv", quakes.to_csv(index=False))
    if not gdacs.empty: zf.writestr("gdacs.csv", gdacs.to_csv(index=False))
    if not fires.empty: zf.writestr("fires.csv", fires.to_csv(index=False))
    if isinstance(f_quakes, pd.DataFrame) and not f_quakes.empty: zf.writestr("aoi_quakes.csv", f_quakes.to_csv(index=False))
    if isinstance(f_gdacs, pd.DataFrame) and not f_gdacs.empty: zf.writestr("aoi_gdacs.csv", f_gdacs.to_csv(index=False))
    if isinstance(f_fires, pd.DataFrame) and not f_fires.empty: zf.writestr("aoi_fires.csv", f_fires.to_csv(index=False))
    zf.writestr("snapshot.json", json.dumps(summary, indent=2))

st.download_button("Download CSVs + snapshot.json (ZIP)", data=csv_zip.getvalue(), file_name="disaster_intel_snapshot.zip", mime="application/zip")

st.markdown("---")
st.caption("Extend this app: add scoring, population exposure, routes, shelter lists, and push alerts via a Make.com webhook.")
