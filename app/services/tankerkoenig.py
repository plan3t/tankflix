import logging
import time
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class TankerKoenigClient:
    base_url = "https://creativecommons.tankerkoenig.de/json/list.php"

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def _cache_key(self, lat: float, lng: float, radius_km: float, fuel_type: str) -> str:
        return f"{fuel_type}:{lat:.5f}:{lng:.5f}:{radius_km:.2f}"

    def fetch_prices(self, lat: float, lng: float, radius_km: float, fuel_type: str) -> list[dict[str, Any]]:
        if not settings.tankerkoenig_api_key:
            logger.warning("Tankerkoenig API key is missing; skipping fetch")
            return []

        key = self._cache_key(lat, lng, radius_km, fuel_type)
        now = time.time()
        min_interval = max(60, settings.tankerkoenig_min_fetch_interval_seconds)
        cached = self._cache.get(key)
        if cached and now - cached[0] < min_interval:
            logger.info("Using cached Tankerkoenig data for %s (age %.1fs)", fuel_type, now - cached[0])
            return cached[1]

        params = {
            "lat": lat,
            "lng": lng,
            "rad": radius_km,
            "sort": "price",
            "type": fuel_type,
            "apikey": settings.tankerkoenig_api_key,
        }

        retries = 3
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(self.base_url, params=params, timeout=self.timeout_seconds)
                response.raise_for_status()
                data = response.json()
                if not data.get("ok"):
                    logger.error("API responded with ok=false for %s: %s", fuel_type, data)
                    return cached[1] if cached else []
                stations = data.get("stations", [])
                self._cache[key] = (now, stations)
                return stations
            except Exception as exc:  # noqa: BLE001
                if attempt == retries:
                    logger.exception("Failed to fetch tankerkoenig data after retries: %s", exc)
                    return cached[1] if cached else []
                backoff = 2 ** (attempt - 1)
                logger.warning("Fetch failed (attempt %s/%s), retrying in %ss", attempt, retries, backoff)
                time.sleep(backoff)
        return cached[1] if cached else []
