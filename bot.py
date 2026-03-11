from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def register_routers():
    from handlers.start import router as start_router
    from handlers.chat import router as chat_router
    from handlers.cart import router as cart_router
    from handlers.payment import router as payment_router
    from handlers.admin import router as admin_router

    # Order matters: more specific handlers first
    dp.include_router(admin_router)   # Admin callbacks (no state filter)
    dp.include_router(payment_router) # Payment FSM states
    dp.include_router(cart_router)    # Cart callbacks
    dp.include_router(start_router)   # Commands (/start, /help, /cart, /products)
    dp.include_router(chat_router)    # AI chat (browsing state + /checkout)
