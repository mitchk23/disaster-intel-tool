
import math
import requests

def geocode(query: str):
    """Return (lat, lon) via Nominatim (OpenStreetMap)."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "HADRI-Disaster-Intel/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    js = r.json()
    if not js:
        raise ValueError("No results")
    return float(js[0]["lat"]), float(js[0]["lon"])

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two WGS84 points in km."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
