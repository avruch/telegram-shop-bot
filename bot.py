from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from config import settings

bot = Bot(token=settings.BOT_TOKEN)

# Use Redis storage when configured (allows restarts without losing cart/checkout state).
# Otherwise fall back to in-memory storage for easy local development.
if settings.REDIS_URL:
    storage = RedisStorage.from_url(settings.REDIS_URL)
else:
    storage = MemoryStorage()

dp = Dispatcher(storage=storage)


def register_routers():
    from handlers.start import router as start_router
    from handlers.chat import router as chat_router
    from handlers.cart import router as cart_router
    from handlers.payment import router as payment_router
    from handlers.admin import router as admin_router
    from handlers.godmode import router as godmode_router

    # Order matters: more specific handlers first
    dp.include_router(godmode_router) # Admin god mode (/godmode command + callbacks)
    dp.include_router(admin_router)   # Admin callbacks (no state filter)
    dp.include_router(payment_router) # Payment FSM states
    dp.include_router(cart_router)    # Cart callbacks + collecting_size state
    dp.include_router(start_router)   # Commands (/start, /help, /cart, /products)
    dp.include_router(chat_router)    # AI chat (browsing state + /checkout)
