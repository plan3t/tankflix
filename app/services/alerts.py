import logging
from datetime import datetime, timedelta

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertLog, AlertState, AppConfig, PriceHistory, StationPrice

logger = logging.getLogger(__name__)


def send_teams_message(webhook_url: str, title: str, lines: list[str]) -> bool:
    if not webhook_url:
        return False
    text = "\n".join([f"**{title}**", *lines])
    payload = {"text": text}
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send Teams message: %s", exc)
        return False


def _get_state(db: Session, key: str) -> AlertState | None:
    return db.scalar(select(AlertState).where(AlertState.state_key == key))


def _set_state(db: Session, key: str, active: bool) -> None:
    state = _get_state(db, key)
    if state is None:
        state = AlertState(state_key=key, active=active)
        db.add(state)
    else:
        state.active = active


def _already_sent(db: Session, dedupe_key: str) -> bool:
    return db.scalar(select(AlertLog).where(AlertLog.dedupe_key == dedupe_key)) is not None


def _mark_sent(db: Session, dedupe_key: str, payload: str) -> None:
    db.add(AlertLog(dedupe_key=dedupe_key, payload=payload))


def process_alerts(db: Session, cfg: AppConfig, fuel_type: str, stations: list[StationPrice]) -> None:
    if not cfg.teams_enabled or not cfg.teams_webhook_url or not stations:
        return

    threshold = cfg.threshold_e5 if fuel_type == "e5" else cfg.threshold_diesel
    now = datetime.utcnow()

    for station in stations:
        state_key = f"below_threshold:{fuel_type}:{station.station_id}"
        below_threshold = station.price > 0 and station.price <= threshold
        state = _get_state(db, state_key)
        was_active = state.active if state else False
        if below_threshold and not was_active:
            dedupe_key = f"threshold:{fuel_type}:{station.station_id}:{now.strftime('%Y%m%d%H%M')}"
            if not _already_sent(db, dedupe_key):
                lines = [
                    f"Kraftstoff: {fuel_type.upper()}",
                    f"Tankstelle: {station.name}",
                    f"Preis: {station.price:.3f} €/L",
                    f"Entfernung: {station.distance_km:.2f} km",
                    f"Zeit: {now.isoformat()} UTC",
                ]
                if send_teams_message(cfg.teams_webhook_url, "Preis unter Grenzwert", lines):
                    _mark_sent(db, dedupe_key, "threshold")
        _set_state(db, state_key, below_threshold)

        prev = db.scalar(
            select(PriceHistory)
            .where(
                PriceHistory.station_id == station.station_id,
                PriceHistory.fuel_type == fuel_type,
                PriceHistory.fetched_at < station.fetched_at,
            )
            .order_by(PriceHistory.fetched_at.desc())
        )

        if prev:
            delta_cents = (station.price - prev.price) * 100
            if abs(delta_cents) >= cfg.strong_change_cents:
                dedupe_window = now - timedelta(minutes=30)
                dedupe_key = f"strong_change:{fuel_type}:{station.station_id}:{int(delta_cents)}:{station.price:.3f}"
                already = db.scalar(
                    select(AlertLog).where(AlertLog.dedupe_key == dedupe_key, AlertLog.sent_at >= dedupe_window)
                )
                if not already:
                    lines = [
                        f"Kraftstoff: {fuel_type.upper()}",
                        f"Tankstelle: {station.name}",
                        f"Preis: {station.price:.3f} €/L",
                        f"Preisänderung: {delta_cents:+.1f} Cent",
                        f"Entfernung: {station.distance_km:.2f} km",
                        f"Zeit: {now.isoformat()} UTC",
                    ]
                    if send_teams_message(cfg.teams_webhook_url, "Starke Preisänderung", lines):
                        _mark_sent(db, dedupe_key, "strong_change")

    if cfg.notify_cheapest_change:
        cheapest = stations[0]
        if fuel_type == "e5":
            old_id = cfg.cheapest_e5_station_id
            if old_id != cheapest.station_id:
                if old_id:
                    send_teams_message(
                        cfg.teams_webhook_url,
                        "Günstigste Tankstelle geändert",
                        [
                            f"Kraftstoff: E5",
                            f"Neue günstigste Tankstelle: {cheapest.name}",
                            f"Preis: {cheapest.price:.3f} €/L",
                            f"Entfernung: {cheapest.distance_km:.2f} km",
                            f"Zeit: {now.isoformat()} UTC",
                        ],
                    )
                cfg.cheapest_e5_station_id = cheapest.station_id
        else:
            old_id = cfg.cheapest_diesel_station_id
            if old_id != cheapest.station_id:
                if old_id:
                    send_teams_message(
                        cfg.teams_webhook_url,
                        "Günstigste Tankstelle geändert",
                        [
                            f"Kraftstoff: Diesel",
                            f"Neue günstigste Tankstelle: {cheapest.name}",
                            f"Preis: {cheapest.price:.3f} €/L",
                            f"Entfernung: {cheapest.distance_km:.2f} km",
                            f"Zeit: {now.isoformat()} UTC",
                        ],
                    )
                cfg.cheapest_diesel_station_id = cheapest.station_id
