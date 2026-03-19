import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from states.states import ShopStates
from services.cart_service import (
    get_or_create_cart,
    add_item,
    remove_item,
    update_item_quantity,
    clear_cart,
    format_cart,
)
from services.inventory_service import get_product
from keyboards.keyboards import cart_keyboard, product_size_keyboard
from services.ai_service import RING_SIZE_GUIDE_URL
from aiogram.exceptions import TelegramBadRequest
import texts

UNCERTAINTY_KEYWORDS = [
    "not sure", "dont know", "don't know", "unsure", "idk", "no idea",
    "help", "what size", "how do i", "how to measure", "i don't know",
    "i dont know", "not sure", "don't know my size", "dont know my size",
]

logger = logging.getLogger(__name__)
router = Router()


async def _refresh_cart_message(query: CallbackQuery, state: FSMContext, user_id: int):
    cart = await get_or_create_cart(user_id)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items) if cart.items else None
    try:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(cart_message_id=query.message.message_id)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass  # content identical, no-op
        else:
            logger.warning(f"Cart edit failed ({e}), sending new message")
            sent = await query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
            await state.update_data(cart_message_id=sent.message_id)
    except Exception as e:
        logger.error(f"Unexpected error refreshing cart: {e}")
        sent = await query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(cart_message_id=sent.message_id)



@router.callback_query(F.data == "show_cart")
async def cb_show_cart(query: CallbackQuery, state: FSMContext):
    user_id = query.from_user.id
    cart = await get_or_create_cart(user_id)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items) if cart.items else None

    data = await state.get_data()
    cart_msg_id = data.get("cart_message_id")

    if cart_msg_id and cart.items:
        try:
            await query.bot.edit_message_text(
                chat_id=query.message.chat.id,
                message_id=cart_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            await query.answer()
            return
        except Exception:
            pass

    sent = await query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    if cart.items:
        await state.update_data(cart_message_id=sent.message_id)
    await query.answer()


@router.callback_query(F.data.startswith("cart_inc:"))
async def cb_cart_inc(query: CallbackQuery, state: FSMContext):
    item_id = int(query.data.split(":")[1])
    await update_item_quantity(item_id, query.from_user.id, +1)
    await _refresh_cart_message(query, state, query.from_user.id)
    await query.answer("➕")


@router.callback_query(F.data.startswith("cart_dec:"))
async def cb_cart_dec(query: CallbackQuery, state: FSMContext):
    item_id = int(query.data.split(":")[1])
    await update_item_quantity(item_id, query.from_user.id, -1)
    await _refresh_cart_message(query, state, query.from_user.id)
    await query.answer("➖")


@router.callback_query(F.data.startswith("cart_remove:"))
async def cb_cart_remove(query: CallbackQuery, state: FSMContext):
    item_id = int(query.data.split(":")[1])
    await remove_item(item_id, query.from_user.id)
    await _refresh_cart_message(query, state, query.from_user.id)
    await query.answer("Removed")


@router.callback_query(F.data == "cart_clear")
async def cb_cart_clear(query: CallbackQuery, state: FSMContext):
    await clear_cart(query.from_user.id)
    await query.message.edit_text(texts.CART_CLEARED, reply_markup=None)
    await state.update_data(cart_message_id=None)
    await query.answer("Cart cleared!")


@router.callback_query(F.data == "checkout")
async def cb_checkout(query: CallbackQuery, state: FSMContext):
    from states.states import ShopStates
    cart = await get_or_create_cart(query.from_user.id)
    if not cart.items:
        await query.answer(texts.CART_EMPTY_ALERT, show_alert=True)
        return
    await state.set_state(ShopStates.collecting_name)
    await state.update_data(checkout_order_id=cart.id)
    await query.message.answer(texts.CHECKOUT_START, parse_mode="Markdown")
    await query.answer()


@router.callback_query(F.data == "show_collection")
async def cb_show_collection(query: CallbackQuery):
    from config import settings
    from keyboards.keyboards import collection_keyboard
    keyboard = collection_keyboard(settings.SHOP_COLLECTION_URL)
    await query.message.answer(texts.COLLECTION_HEADER, reply_markup=keyboard)
    await query.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()


@router.callback_query(F.data.startswith("want_product:"))
async def cb_want_product(query: CallbackQuery, state: FSMContext):
    """User tapped Add to Cart — ask them for their size."""
    product_id = int(query.data.split(":")[1])
    product = await get_product(product_id)
    if not product:
        await query.answer("Product not found.", show_alert=True)
        return

    await state.set_state(ShopStates.collecting_size)
    await state.update_data(pending_product_id=product_id, pending_product_name=product.name)
    await query.message.answer(
        texts.ASK_SIZE.format(product_name=product.name),
        parse_mode="Markdown",
    )
    await query.answer()


@router.message(ShopStates.collecting_size)
async def collect_size(message: Message, state: FSMContext):
    """Receive the customer's size, or guide them if they're unsure."""
    if not message.text:
        await message.answer("Please type your size as a text message.")
        return

    text_lower = message.text.strip().lower()

    # Customer doesn't know their size — send guide and wait
    if any(kw in text_lower for kw in UNCERTAINTY_KEYWORDS):
        await message.answer(texts.SIZE_GUIDE_REMINDER.format(ring_size_guide=RING_SIZE_GUIDE_URL))
        return  # Stay in collecting_size state

    data = await state.get_data()
    product_id = data.get("pending_product_id")
    product_name = data.get("pending_product_name", f"Product #{product_id}")
    size = message.text.strip()

    cart = await add_item(message.from_user.id, product_id, size, 1)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items)

    cart_msg_id = data.get("cart_message_id")
    if cart_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=cart_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            await message.answer(texts.ITEM_ADDED.format(product_name=product_name, size=size), parse_mode="Markdown")
            await state.set_state(ShopStates.browsing)
            await state.update_data(pending_product_id=None, pending_product_name=None)
            return
        except Exception:
            pass

    sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await message.answer(texts.ITEM_ADDED.format(product_name=product_name, size=size), parse_mode="Markdown")
    await state.set_state(ShopStates.browsing)
    await state.update_data(
        cart_message_id=sent.message_id,
        pending_product_id=None,
        pending_product_name=None,
    )
