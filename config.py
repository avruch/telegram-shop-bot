from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
    )

    BOT_TOKEN: str
    ADMIN_CHAT_ID: int
    GOOGLE_API_KEY: str = "YOUR_GOOGLE_API_KEY"
    GOOGLE_SHEETS_ID: str = "YOUR_GOOGLE_SHEET_ID"
    GOOGLE_SHEETS_EXPORT_ID: str = "YOUR_EXPORT_SHEET_ID"
    WEBHOOK_URL: str = ""
    REDIS_URL: str = ""
    DATABASE_URL: str = "postgresql://localhost/shop"
    PAYPAL_LINK: str = "https://paypal.me/yourshop"
    SHOP_COLLECTION_URL: str
    SHOP_NAME: str
    BANNER_FILENAME: str


settings = Settings()
