
# HADRI – Disaster Intelligence (Starter App)

A tiny, phone-friendly Streamlit app that:
- Pulls live hazards: **USGS earthquakes**, **GDACS all-hazards (RSS)**, **NASA FIRMS fires (24h)**.
- Lets you set an **AOI** by place name and a **radius**, then filters events within range.
- Exports a quick snapshot (`snapshot.json`) and CSVs for the AOI and raw feeds.

> This is a scaffold to get you shipping fast. Extend it with scoring, exposure, routing, shelters, and Make.com webhooks.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). It adjusts to mobile screens automatically.

## Privacy & Safety

- Runs on your machine. You decide what gets shared.
- Add outbound sharing only via explicit buttons/webhooks you own.
- For Make.com, add a button that POSTs `snapshot.json` to your webhook URL.

## Extend quickly

- **More feeds:** ReliefWeb, EONET, JMA, JRC Floods, local agencies.
- **Scoring:** Add severity × exposure × access constraints.
- **Exposure:** Pull admin boundaries (GADM) and population (WorldPop) to estimate population-in-radius.
- **Routing:** Integrate OpenRouteService for access routes.
- **Notifications:** Add Slack/Telegram/Email via your infra.

## Notes

- NASA FIRMS 24h CSV is public but large. For production, consider authenticated tiles or regional subsets.
- GDACS RSS lat/lon is inconsistent across items; you can enrich with their API if needed.
- Respect each data provider's usage policy.
