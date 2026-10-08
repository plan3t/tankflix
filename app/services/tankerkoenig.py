import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchOutcome:
    state: str
    fetched_at: datetime | None = None
    cached: bool = False


class TankerKoenigClient:
    base_url = "https://creativecommons.tankerkoenig.de/json/list.php"

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self.outcomes: dict[str, FetchOutcome] = {}

    def _cache_key(self, lat: float, lng: float, radius_km: float, fuel_type: str) -> str:
        return f"{fuel_type}:{lat:.5f}:{lng:.5f}:{radius_km:.2f}"

    def fetch_prices(self, lat: float, lng: float, radius_km: float, fuel_type: str) -> list[dict[str, Any]]:
        if not settings.tankerkoenig_api_key:
            self.outcomes[fuel_type] = FetchOutcome("missing_key")
            logger.warning("Tankerkoenig API key is missing; skipping fetch")
            return []

        key = self._cache_key(lat, lng, radius_km, fuel_type)
        now = time.time()
        min_interval = max(60, settings.tankerkoenig_min_fetch_interval_seconds)
        cached = self._cache.get(key)
        if cached and now - cached[0] < min_interval:
            self.outcomes[fuel_type] = FetchOutcome("ok", datetime.utcfromtimestamp(cached[0]), cached=True)
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
                    self.outcomes[fuel_type] = FetchOutcome("error")
                    logger.error("API responded with ok=false for %s", fuel_type)
                    return cached[1] if cached else []
                stations = data.get("stations", [])
                if not isinstance(stations, list) or not all(isinstance(item, dict) for item in stations):
                    raise ValueError("Invalid station response")
                fetched = time.time()
                self._cache[key] = (fetched, stations)
                self.outcomes[fuel_type] = FetchOutcome("ok", datetime.utcfromtimestamp(fetched))
                return stations
            except Exception as exc:  # noqa: BLE001
                if attempt == retries:
                    self.outcomes[fuel_type] = FetchOutcome("error")
                    # Request exceptions may contain the API key in their URL.
                    logger.error("Failed to fetch tankerkoenig data after retries (%s)", type(exc).__name__)
                    return cached[1] if cached else []
                backoff = 2 ** (attempt - 1)
                logger.warning("Fetch failed (attempt %s/%s), retrying in %ss", attempt, retries, backoff)
                time.sleep(backoff)
        return cached[1] if cached else []
