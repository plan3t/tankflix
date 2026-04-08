import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password, verify_password
from app.config import settings
from app.database import Base, engine, get_db
from app.models import AdminUser, AppConfig, StationPrice
from app.services.poller import PricePoller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

poller = PricePoller()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        seed_defaults(db)
    await poller.start()
    yield
    await poller.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def seed_defaults(db: Session) -> None:
    config = db.get(AppConfig, 1)
    if config is None:
        db.add(
            AppConfig(
                id=1,
                origin_address=settings.default_origin_address,
                origin_lat=settings.default_origin_lat,
                origin_lng=settings.default_origin_lng,
                poll_interval_seconds=max(300, settings.poll_interval_seconds),
            )
        )


    elif not config.origin_address and config.origin_lat == 52.52 and config.origin_lng == 13.405:
        config.origin_address = settings.default_origin_address
        config.origin_lat = settings.default_origin_lat
        config.origin_lng = settings.default_origin_lng

    admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    if admin is None:
        db.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
    db.commit()


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def require_admin(request: Request) -> None:
    if not request.session.get("admin_user"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, fuel: str = "e5", db: Session = Depends(get_db)):
    fuel = fuel if fuel in {"e5", "diesel"} else "e5"
    cfg = db.get(AppConfig, 1)
    rows = db.scalars(select(StationPrice).where(StationPrice.fuel_type == fuel)).all()
    rows.sort(key=lambda row: (row.price, row.distance_km))
    last_update = rows[0].fetched_at if rows else None
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "fuel": fuel,
            "stations": rows,
            "last_update": last_update,
            "config": cfg,
        },
    )


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "csrf_token": ensure_csrf(request), "error": None},
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if csrf_token != request.session.get("csrf_token"):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "csrf_token": ensure_csrf(request), "error": "Ungültiger Login"},
            status_code=401,
        )
    request.session["admin_user"] = username
    return RedirectResponse(url="/admin", status_code=302)


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    cfg = db.get(AppConfig, 1)
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "config": cfg, "csrf_token": ensure_csrf(request), "saved": False, "now": datetime.utcnow()},
    )


@app.post("/admin", response_class=HTMLResponse)
def admin_save(
    request: Request,
    origin_address: str = Form(""),
    origin_lat: float = Form(...),
    origin_lng: float = Form(...),
    radius_km: float = Form(...),
    threshold_e5: float = Form(...),
    threshold_diesel: float = Form(...),
    strong_change_cents: float = Form(...),
    poll_interval_seconds: int = Form(...),
    teams_webhook_url: str = Form(""),
    csrf_token: str = Form(...),
    teams_enabled: str | None = Form(None),
    only_open: str | None = Form(None),
    notify_cheapest_change: str | None = Form(None),
    db: Session = Depends(get_db),
):
    require_admin(request)
    if csrf_token != request.session.get("csrf_token"):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    cfg = db.get(AppConfig, 1)
    cfg.origin_address = origin_address.strip()
    cfg.origin_lat = origin_lat
    cfg.origin_lng = origin_lng
    cfg.radius_km = radius_km
    cfg.threshold_e5 = threshold_e5
    cfg.threshold_diesel = threshold_diesel
    cfg.strong_change_cents = strong_change_cents
    cfg.poll_interval_seconds = max(300, poll_interval_seconds)
    cfg.teams_webhook_url = teams_webhook_url.strip()
    cfg.teams_enabled = bool(teams_enabled)
    cfg.only_open = bool(only_open)
    cfg.notify_cheapest_change = bool(notify_cheapest_change)
    db.commit()

    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "config": cfg, "csrf_token": ensure_csrf(request), "saved": True, "now": datetime.utcnow()},
    )
