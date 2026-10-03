import json
import logging
import urllib.request

from fastapi import APIRouter, HTTPException, Query, Request

from ...config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_settings(request: Request):
    return getattr(request.app.state, "settings", None) or get_settings()


@router.get("/weather/risk")
def get_weather_risk(
    request: Request,
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
) -> dict[str, object]:
    settings = _get_settings(request)
    if not settings.feature_weather_risk:
        raise HTTPException(status_code=403, detail="Weather risk feature is disabled")

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FieldnoteApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"status": "ok", "data": data}
    except Exception as exc:
        logger.warning(f"Failed to fetch from Open-Meteo: {exc}")
        return {
            "status": "fallback",
            "data": {
                "current": {
                    "temperature_2m": 22.0,
                    "relative_humidity_2m": 70.0,
                    "precipitation": 0.0,
                },
                "daily": {
                    "time": [],
                    "temperature_2m_max": [],
                    "temperature_2m_min": [],
                    "precipitation_sum": [],
                },
            },
        }
