from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    ADMIN_CHAT_ID: int
    GOOGLE_API_KEY: str
    WEBHOOK_URL: str = ""
    DATABASE_PATH: str = "shop.db"
    PAYPAL_LINK: str = "https://paypal.me/yourshop"
    SHOP_COLLECTION_URL: str = ""
    SHOP_NAME: str = "My Awesome Shop"


settings = Settings()
