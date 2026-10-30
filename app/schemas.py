from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    # Administrators cannot be self-registered, so "admin" is not an accepted value here.
    role: Literal["customer", "farmer_seller", "enumerator", "nisr"] = "customer"
    organisation: str | None = Field(default=None, max_length=200)


class AuthOut(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    role: str
    status: str
    message: str | None = None


class UserUpdate(BaseModel):
    role: Literal["customer", "farmer_seller", "enumerator", "nisr", "admin"] | None = None
    status: Literal["pending", "active", "disabled"] | None = None


class PriceIn(BaseModel):
    product_id: int
    market_id: int
    price_rwf: int = Field(gt=0, le=10_000_000)
    unit: str = Field(min_length=1, max_length=30)
    observed_on: date
    collection_method: str = Field(default="enumerator visit", max_length=100)
    source_id: int | None = None

    @field_validator("observed_on")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("observed_on cannot be in the future")
        return v


class ReviewIn(BaseModel):
    action: Literal["approve", "reject", "correct"]
    note: str | None = Field(default=None, max_length=1000)
    new_price_rwf: int | None = Field(default=None, gt=0, le=10_000_000)
