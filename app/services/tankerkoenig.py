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

    def fetch_prices(self, lat: float, lng: float, radius_km: float, fuel_type: str) -> list[dict[str, Any]]:
        if not settings.tankerkoenig_api_key:
            logger.warning("Tankerkoenig API key is missing; skipping fetch")
            return []

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
                    return []
                return data.get("stations", [])
            except Exception as exc:  # noqa: BLE001
                if attempt == retries:
                    logger.exception("Failed to fetch tankerkoenig data after retries: %s", exc)
                    return []
                backoff = 2 ** (attempt - 1)
                logger.warning("Fetch failed (attempt %s/%s), retrying in %ss", attempt, retries, backoff)
                time.sleep(backoff)
        return []
