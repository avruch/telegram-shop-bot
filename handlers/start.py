from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from states.states import ShopStates
from config import settings

router = Router()

WELCOME_MESSAGE = """👋 Welcome to *{shop_name}*!

I'm Alex, your personal shopping assistant. I'm here to help you find exactly what you're looking for.

Here's what I can do:
• 🛍 Show you our latest collection
• 💬 Answer any questions about products
• 🛒 Manage your shopping cart
• 📦 Help you place an order

Just chat with me naturally! Try saying:
  _"Show me your products"_
  _"I'm looking for a hoodie in size M"_
  _"What do you have in stock?"_
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ShopStates.browsing)
    await state.update_data(conversation_history=[], cart_message_id=None)
    await message.answer(
        WELCOME_MESSAGE.format(shop_name=settings.SHOP_NAME),
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """*Available Commands:*

/start — Restart and clear conversation
/cart — View your current cart
/products — Browse all products
/checkout — Begin the checkout process
/help — Show this help message

Or just chat naturally — I understand plain English! 😊"""
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("cart"))
async def cmd_cart(message: Message, state: FSMContext):
    from services.cart_service import get_or_create_cart, format_cart
    from keyboards.keyboards import cart_keyboard

    cart = await get_or_create_cart(message.from_user.id)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items) if cart.items else None
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(Command("products"))
async def cmd_products(message: Message, state: FSMContext):
    from services.inventory_service import get_all_products
    from keyboards.keyboards import product_size_keyboard

    products = await get_all_products()
    if not products:
        await message.answer("No products available right now.")
        return

    await message.answer("Here are all our products:\n", parse_mode="Markdown")
    for product in products:
        caption = (
            f"*{product.name}*\n"
            f"{product.description}\n"
            f"💲 *${product.price:.2f}*\n"
            f"Available sizes: {', '.join(product.available_sizes()) or 'Out of stock'}"
        )
        keyboard = product_size_keyboard(product)
        if product.image_url:
            try:
                await message.answer_photo(
                    product.image_url,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                continue
            except Exception:
                pass
        await message.answer(caption, reply_markup=keyboard, parse_mode="Markdown")
