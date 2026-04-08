from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppConfig(Base):
    __tablename__ = "app_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    origin_address: Mapped[str] = mapped_column(String(255), default=settings.default_origin_address)
    origin_lat: Mapped[float] = mapped_column(Float, default=settings.default_origin_lat)
    origin_lng: Mapped[float] = mapped_column(Float, default=settings.default_origin_lng)
    radius_km: Mapped[float] = mapped_column(Float, default=5.0)
    threshold_e5: Mapped[float] = mapped_column(Float, default=1.80)
    threshold_diesel: Mapped[float] = mapped_column(Float, default=1.70)
    strong_change_cents: Mapped[float] = mapped_column(Float, default=5.0)
    teams_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    teams_webhook_url: Mapped[str] = mapped_column(Text, default="")
    only_open: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_cheapest_change: Mapped[bool] = mapped_column(Boolean, default=False)
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    cheapest_e5_station_id: Mapped[str] = mapped_column(String(100), default="")
    cheapest_diesel_station_id: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StationPrice(Base):
    __tablename__ = "station_prices"
    __table_args__ = (UniqueConstraint("station_id", "fuel_type", name="uq_station_fuel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), default="")
    street: Mapped[str] = mapped_column(String(255), default="")
    place: Mapped[str] = mapped_column(String(255), default="")
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AlertLog(Base):
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    payload: Mapped[str] = mapped_column(Text, default="")


class AlertState(Base):
    __tablename__ = "alert_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    state_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
