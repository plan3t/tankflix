"""Read-only presentation data shared by the station overview and history API."""
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AlertLog, AppConfig, FetchStatus, PriceHistory, StationPrice


def utc_iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def overview_data(db: Session, cfg: AppConfig, fuel: str) -> dict:
    now = datetime.utcnow()
    rows = list(db.scalars(select(StationPrice).where(StationPrice.fuel_type == fuel)))
    rows.sort(key=lambda row: (row.price, row.distance_km, row.station_id))
    last_update = max((row.fetched_at for row in rows), default=None)
    stale_seconds = max(600, cfg.poll_interval_seconds * 2, settings.tankerkoenig_min_fetch_interval_seconds * 2)
    history = list(db.scalars(select(PriceHistory).where(
        PriceHistory.fuel_type == fuel, PriceHistory.fetched_at >= now - timedelta(days=7)
    ).order_by(PriceHistory.fetched_at, PriceHistory.id)))
    histories: dict[str, list[float]] = {}
    for item in history:
        histories.setdefault(item.station_id, []).append(round(item.price, 3))

    meta = {}
    payload = []
    threshold = cfg.threshold_e5 if fuel == "e5" else cfg.threshold_diesel
    for row in rows:
        previous = db.scalar(select(PriceHistory).where(
            PriceHistory.station_id == row.station_id,
            PriceHistory.fuel_type == fuel,
            PriceHistory.fetched_at < row.fetched_at,
        ).order_by(PriceHistory.fetched_at.desc(), PriceHistory.id.desc()).limit(1))
        delta = (row.price - previous.price) * 100 if previous else None
        last_alert = db.scalar(select(func.max(AlertLog.sent_at)).where(or_(
            AlertLog.dedupe_key.startswith(f"threshold:{fuel}:{row.station_id}:", autoescape=True),
            AlertLog.dedupe_key.startswith(f"strong_change:{fuel}:{row.station_id}:", autoescape=True),
        )))
        meta[row.station_id] = {
            "below_threshold": 0 < row.price <= threshold,
            "strong_drop": delta is not None and delta <= -cfg.strong_change_cents,
            "strong_rise": delta is not None and delta >= cfg.strong_change_cents,
            "delta_cents": round(delta, 1) if delta is not None else None,
            "previous_price": previous.price if previous else None,
            "previous_at": utc_iso(previous.fetched_at) if previous else None,
            "threshold": threshold,
            "strong_change_cents": cfg.strong_change_cents,
            "last_alert_at": utc_iso(last_alert),
            "stale": (now - row.fetched_at).total_seconds() > stale_seconds,
        }
        payload.append({
            "id": row.station_id, "name": row.name, "brand": row.brand or "",
            "street": row.street or "", "place": row.place or "",
            "lat": row.lat, "lng": row.lng, "price": row.price,
            "distance_km": row.distance_km, "is_open": row.is_open,
            "fetched_at": utc_iso(row.fetched_at), "meta": meta[row.station_id],
        })

    status = db.get(FetchStatus, fuel)
    state = status.state if status else "pending"
    if not settings.tankerkoenig_api_key:
        state = "missing_key"
    # Existing installations have snapshots but no fetch-status rows yet.
    last_success = (status.last_success_at if status else None) or last_update
    is_stale = bool(last_success and (now - last_success).total_seconds() > stale_seconds)
    messages = {
        "missing_key": "Kein API-Key hinterlegt. Live-Preise sind noch nicht verfügbar.",
        "error": "Der letzte Preisabruf ist fehlgeschlagen. Vorhandene Preise bleiben sichtbar.",
        "empty": "Der letzte Abruf war erfolgreich, aber es gibt keine passenden Tankstellen im Suchradius.",
        "pending": "Ein neuer Preisabruf steht noch aus.",
        "ok": "Der letzte Preisabruf war erfolgreich.",
    }
    return {
        "stations": rows, "last_update": last_update,
        "brands": sorted({row.brand for row in rows if row.brand}),
        "station_meta": meta, "history_by_station": histories,
        "stations_payload": payload,
        "fetch_health": {"state": state, "message": messages.get(state, messages["pending"]),
                         "last_success_at": utc_iso(last_success), "stale": is_stale},
        "stale_seconds": stale_seconds,
    }
