import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

# Cache weather data for 30 minutes to avoid hammering the API
_weather_cache = {"data": None, "timestamp": 0}
CACHE_TTL_SECONDS = 1800


def get_external_weather() -> dict:
    """Fetch current weather from Open-Meteo API. Results are cached for 30 minutes."""
    now = time.time()
    if _weather_cache["data"] and (now - _weather_cache["timestamp"]) < CACHE_TTL_SECONDS:
        return _weather_cache["data"]

    lat = os.environ.get("OPEN_METEO_LATITUDE", "48.8566")
    lon = os.environ.get("OPEN_METEO_LONGITUDE", "2.3522")

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        current = data["current"]
        result = {
            "external_temperature": current["temperature_2m"],
            "external_humidity": current["relative_humidity_2m"],
            "external_wind_speed": current["wind_speed_10m"],
            "weather_code": current["weather_code"],
        }
        _weather_cache["data"] = result
        _weather_cache["timestamp"] = now
        logger.info("Fetched external weather: %.1fC, %d%% humidity",
                     result["external_temperature"], result["external_humidity"])
        return result
    except Exception:
        logger.exception("Failed to fetch external weather")
        return {}
