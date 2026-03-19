from pathlib import Path
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from states.states import ShopStates
from config import settings
import texts

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ShopStates.browsing)
    await state.update_data(conversation_history=[], cart_message_id=None)

    welcome_text = texts.WELCOME.format(shop_name=settings.SHOP_NAME)
    banner_path = Path(__file__).parent.parent / settings.BANNER_FILENAME

    if settings.BANNER_FILENAME and banner_path.exists():
        await message.answer_photo(
            FSInputFile(banner_path),
            caption=welcome_text,
            parse_mode="Markdown",
        )
    else:
        await message.answer(welcome_text, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(texts.HELP, parse_mode="Markdown")


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
        await message.answer(texts.NO_PRODUCTS)
        return

    await message.answer(texts.PRODUCTS_HEADER, parse_mode="Markdown")
    for product in products:
        caption = texts.PRODUCT_CAPTION.format(
            name=product.name,
            description=product.description,
            price=product.price,
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
