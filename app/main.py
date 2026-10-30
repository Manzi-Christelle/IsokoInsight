from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, ensure_schema, get_db
from .models import OfficialIndicator, OfficialSeries, PriceObservation
from .routers import admin, auth, chat, climate, forecast, geo, indicators, nisr, official, prices

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="IsokoInsight Rwanda - Food Price Monitoring API",
    description="Official NISR CPI statistics and verified local market prices, kept separate.",
    version="0.1.0",
)

if settings.app_env == "production" and settings.secret_key == "change-me-in-production":
    raise RuntimeError("Set a strong SECRET_KEY before running in production.")

Base.metadata.create_all(engine)  # MVP only; use Alembic migrations for schema changes later
ensure_schema(engine)

app.include_router(auth.router)
app.include_router(prices.router)
app.include_router(official.router)
app.include_router(admin.router)
app.include_router(geo.router)
app.include_router(chat.router)
app.include_router(nisr.router)
app.include_router(indicators.router)
app.include_router(climate.router)
app.include_router(forecast.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/api/summary", tags=["system"])
def summary(db: Session = Depends(get_db)):
    verified = db.query(PriceObservation).filter_by(status="verified")
    latest = db.query(OfficialIndicator).order_by(OfficialIndicator.period.desc()).first()
    return {
        "verified_observations": verified.count(),
        "pending_observations": db.query(PriceObservation).filter_by(status="pending").count(),
        "synthetic_observations": db.query(PriceObservation).filter_by(is_synthetic=True).count(),
        "markets_with_data": db.query(func.count(func.distinct(PriceObservation.market_id)))
                               .filter_by(status="verified").scalar(),
        "official_series": db.query(OfficialSeries).count(),
        "latest_price_date": (lambda d: d.isoformat() if d else None)(
            db.query(func.max(PriceObservation.observed_on)).filter_by(status="verified").scalar()),
    }


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def welcome():
    """Welcome page with the slideshow. It links on to the dashboard."""
    return FileResponse(STATIC / "welcome.html")


@app.get("/dashboard", include_in_schema=False)
def index():
    """The main dashboard with all the information."""
    return FileResponse(STATIC / "index.html")


@app.get("/account", include_in_schema=False)
def account_page():
    """Sign in and create an account."""
    return FileResponse(STATIC / "account.html")
