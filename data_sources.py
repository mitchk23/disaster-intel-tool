import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
from io import StringIO

def _now_utc():
    return datetime.now(timezone.utc)

def fetch_usgs_quakes(hours_back=24):
    """USGS earthquakes past N hours."""
    # Use official day/hour feeds; hours_back is applied by choosing the feed
    url = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
        if hours_back <= 1 else
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    js = r.json()
    rows = []
    for f in js.get("features", []):
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None, None])
        rows.append({
            "time_utc": datetime.utcfromtimestamp((props.get("time") or 0)/1000).replace(tzinfo=timezone.utc),
            "magnitude": props.get("mag"),
            "place": props.get("place"),
            "latitude": coords[1],
            "longitude": coords[0],
            "depth_km": coords[2],
            "url": props.get("url")
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("time_utc", ascending=False).reset_index(drop=True)
    return df

def fetch_gdacs_events(hours_back=24):
    """GDACS global all-hazards via RSS."""
    url = "https://www.gdacs.org/xml/rss.xml"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = root.findall(".//item")
    rows = []
    cutoff = _now_utc() - timedelta(hours=hours_back)
    for it in items:
        title = (it.findtext("title") or "").strip()
        link = it.findtext("link") or ""
        pubdate = it.findtext("{http://purl.org/dc/elements/1.1/}date") or it.findtext("pubDate") or ""
        lat = it.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}lat")
        lon = it.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}long") or it.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}lon")
        try:
            t = datetime.fromisoformat(pubdate.replace("Z","+00:00"))
        except Exception:
            t = _now_utc()
        if t < cutoff:
            continue
        rows.append({
            "time_utc": t,
            "title": title,
            "url": link,
            "latitude": float(lat) if lat else None,
            "longitude": float(lon) if lon else None,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("time_utc", ascending=False).reset_index(drop=True)
    return df

def fetch_nasa_firms(hours_back=24):
    """NASA FIRMS global fires (VIIRS NRT, last 24h) with header + fallback."""
    primary = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/viirs-nrt/viirs_global_24h.csv"
    fallbacks = [
        # Common alternates (NASA occasionally shuffles names/casing)
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/viirs/viirs_global_24h.csv",
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/viirs-nrt/VIIRS_I_Global_24h.csv",
    ]
    headers = {"User-Agent": "HADRI-Disaster-Intel/1.0"}

    def try_read(url):
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return pd.read_csv(StringIO(r.text))

    df = None
    try:
        df = try_read(primary)
    except Exception:
        for u in fallbacks:
            try:
                df = try_read(u)
                break
            except Exception:
                continue
    if df is None or df.empty:
        return pd.DataFrame(columns=["time_utc","latitude","longitude","brightness","confidence"])

    # Build a datetime column (UTC)
    try:
        dt = pd.to_datetime(
            df["acq_date"] + " " + df["acq_time"].astype(str).str.zfill(4),
            format="%Y-%m-%d %H%M",
            utc=True
        )
        df["time_utc"] = dt
    except Exception:
        df["time_utc"] = pd.NaT

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    if "time_utc" in df:
        df = df[df["time_utc"] >= cutoff]

    out = df.rename(columns={
        "latitude": "latitude",
        "longitude": "longitude",
        "bright_ti4": "brightness",
        "confidence": "confidence"
    })[["time_utc", "latitude", "longitude", "brightness", "confidence"]]

    return out.sort_values("time_utc", ascending=False).reset_index(drop=True)
    return out
