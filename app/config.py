from datetime import date

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./isoko.db"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_minutes: int = 480
    admin_email: str = "admin@example.com"
    admin_password: str = "ChangeThisPassword123"
    price_change_threshold_pct: float = 25.0
    cpi_mom_threshold_pct: float = 5.0
    # District map colour bands: index above yellow = medium, above red = critical
    district_yellow_pct: float = 5.0
    district_red_pct: float = 15.0
    district_min_products: int = 2
    # Dates the price search covers. Searches outside this window show 'No data found'.
    price_range_start: date = date(2000, 1, 1)
    price_range_end: date = date(2026, 8, 31)


settings = Settings()
