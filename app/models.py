"""Database schema.

Two separate data streams are kept apart on purpose:
  A. Official statistics (OfficialSeries / OfficialValue / OfficialIndicator) - national CPI.
  B. Local market observations (PriceObservation) - item-level prices with unit, date,
     source and verification status.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    publisher: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(String(100))
    downloaded_on: Mapped[date | None] = mapped_column(Date)
    transformations: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str | None] = mapped_column(String(200))
    organisation: Mapped[str | None] = mapped_column(String(200))
    # customer | farmer_seller | enumerator | nisr | admin  (see app/permissions.py)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    # pending (awaiting approval) | active | disabled
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(100))
    standard_unit: Mapped[str] = mapped_column(String(30))  # e.g. "kg"


class Market(Base):
    __tablename__ = "markets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    district: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("name", "district"),)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    price_rwf: Mapped[int] = mapped_column(Integer)  # whole Rwandan francs
    unit: Mapped[str] = mapped_column(String(30))
    observed_on: Mapped[date] = mapped_column(Date)
    collection_method: Mapped[str] = mapped_column(String(100), default="enumerator visit")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|verified|rejected
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product")
    market = relationship("Market")
    source = relationship("DataSource")

    __table_args__ = (Index("ix_obs_lookup", "product_id", "market_id", "unit", "observed_on"),)


class VerificationLog(Base):
    """Audit trail: every admin decision is kept, never overwritten."""
    __tablename__ = "verification_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey("price_observations.id"))
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(20))  # approve | reject | correct
    note: Mapped[str | None] = mapped_column(Text)
    old_price_rwf: Mapped[int | None] = mapped_column(Integer)
    new_price_rwf: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfficialSeries(Base):
    __tablename__ = "official_series"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    group: Mapped[str] = mapped_column(String(20))  # headline | division | food_subgroup
    weight: Mapped[float | None] = mapped_column(Float)  # out of 10,000
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source = relationship("DataSource")


class OfficialValue(Base):
    __tablename__ = "official_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("official_series.id"))
    period: Mapped[date] = mapped_column(Date)  # first day of the month
    index_value: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("series_id", "period"),)


class OfficialIndicator(Base):
    """Published headline figures (e.g. NISR's inflation rate) quoted as released."""
    __tablename__ = "official_indicators"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    period: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source = relationship("DataSource")
    __table_args__ = (UniqueConstraint("name", "period"),)


class Alert(Base):
    """A review flag. It is NOT a claim that a shortage or fraud exists."""
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # price_observation | cpi_series
    ref: Mapped[str] = mapped_column(String(100))
    period: Mapped[date | None] = mapped_column(Date)
    change_pct: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | reviewed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClimateObservation(Base):
    """Monthly rainfall and mean temperature for one district. SYNTHETIC demo rows (source is_synthetic).
    Logic lives in app/climate.py."""
    __tablename__ = "climate_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)  # 1 to 12
    rain_mm: Mapped[float] = mapped_column(Float)
    temp_c: Mapped[float] = mapped_column(Float)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source = relationship("DataSource")
    __table_args__ = (UniqueConstraint("district", "year", "month"),)


class IndicatorValue(Base):
    """One value of a district indicator (or a national figure) for a year and, where the survey
    reports them, a season. Keys come from app/indicators.py. Season is "" for annual indicators."""
    __tablename__ = "indicator_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    indicator: Mapped[str] = mapped_column(String(60), index=True)
    district: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    season: Mapped[str] = mapped_column(String(2), default="")  # "", "A", "B" or "C"
    value: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source = relationship("DataSource")
    __table_args__ = (UniqueConstraint("indicator", "district", "year", "season"),)
