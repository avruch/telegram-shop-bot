"""
AI-Powered Telegram E-Commerce Bot
Entry point — supports both webhook (production) and polling (development) modes.

Usage:
  Development (polling):  python main.py
  Production (webhook):   Set WEBHOOK_URL in .env, then run with uvicorn:
                          uvicorn main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from aiogram.types import Update

from bot import bot, dp, register_routers
from database.db import init_db
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = f"/webhook/{settings.BOT_TOKEN}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    register_routers()

    if settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.info("No WEBHOOK_URL set — use polling mode (python main.py)")

    yield

    # Shutdown
    if settings.WEBHOOK_URL:
        await bot.delete_webhook()

    # Close bot session and storage gracefully
    await bot.session.close()
    try:
        await dp.storage.close()
        await dp.storage.wait_closed()
    except Exception:
        pass

    logger.info("Bot shutdown complete.")


app = FastAPI(lifespan=lifespan, title="Telegram Shop Bot")


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/health")
async def health_check():
    return {"status": "ok", "shop": settings.SHOP_NAME}


async def run_polling():
    """Development mode: run with long-polling instead of webhook."""
    logger.info("Starting bot in polling mode...")
    await init_db()
    register_routers()
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(run_polling())
