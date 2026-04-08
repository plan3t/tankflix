import asyncio
import logging
from datetime import datetime

from sqlalchemy import delete, select

from app.config import settings
from app.database import SessionLocal
from app.models import AppConfig, PriceHistory, StationPrice
from app.services.alerts import process_alerts
from app.services.distance import haversine_distance_km
from app.services.tankerkoenig import TankerKoenigClient

logger = logging.getLogger(__name__)


class PricePoller:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self.client = TankerKoenigClient(timeout_seconds=settings.request_timeout_seconds)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Price poller started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Price poller stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Polling failed: %s", exc)

            interval = self._get_interval()
            await asyncio.sleep(interval)

    def _get_interval(self) -> int:
        with SessionLocal() as db:
            cfg = db.get(AppConfig, 1)
            db_interval = cfg.poll_interval_seconds if cfg else settings.poll_interval_seconds
        return max(300, db_interval)

    def poll_once(self) -> None:
        with SessionLocal() as db:
            cfg = db.get(AppConfig, 1)
            if cfg is None:
                cfg = AppConfig(id=1, poll_interval_seconds=max(300, settings.poll_interval_seconds))
                db.add(cfg)
                db.commit()
                db.refresh(cfg)

            for fuel_type in ["e5", "diesel"]:
                stations = self.client.fetch_prices(cfg.origin_lat, cfg.origin_lng, cfg.radius_km, fuel_type)
                if not stations:
                    continue

                db.execute(delete(StationPrice).where(StationPrice.fuel_type == fuel_type))
                now = datetime.utcnow()
                items: list[StationPrice] = []
                for raw in stations:
                    price = raw.get("price")
                    if price is None:
                        continue
                    is_open = bool(raw.get("isOpen", False))
                    if cfg.only_open and not is_open:
                        continue
                    dist = raw.get("dist")
                    if dist is None:
                        dist = haversine_distance_km(cfg.origin_lat, cfg.origin_lng, raw.get("lat", 0.0), raw.get("lng", 0.0))
                    item = StationPrice(
                        station_id=raw.get("id", ""),
                        fuel_type=fuel_type,
                        name=raw.get("name", "Unbekannt"),
                        brand=raw.get("brand") or "",
                        street=raw.get("street") or "",
                        place=raw.get("place") or "",
                        lat=float(raw.get("lat", 0.0)),
                        lng=float(raw.get("lng", 0.0)),
                        is_open=is_open,
                        price=float(price),
                        distance_km=float(dist),
                        fetched_at=now,
                    )
                    items.append(item)
                    db.add(
                        PriceHistory(
                            station_id=item.station_id,
                            fuel_type=fuel_type,
                            price=item.price,
                            fetched_at=now,
                        )
                    )

                items.sort(key=lambda i: (i.price, i.distance_km))
                for it in items:
                    db.add(it)

                process_alerts(db, cfg, fuel_type, items)

            db.commit()
            logger.info("Polling cycle finished at %s", datetime.utcnow().isoformat())
