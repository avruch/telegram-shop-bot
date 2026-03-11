import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from services.cart_service import (
    get_or_create_cart,
    add_item,
    remove_item,
    update_item_quantity,
    clear_cart,
    format_cart,
)
from services.inventory_service import check_stock
from keyboards.keyboards import cart_keyboard, product_size_keyboard

logger = logging.getLogger(__name__)
router = Router()


async def _refresh_cart_message(query: CallbackQuery, state: FSMContext, user_id: int):
    cart = await get_or_create_cart(user_id)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items) if cart.items else None
    try:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        await query.answer("Cart updated!")
    await state.update_data(cart_message_id=query.message.message_id)


@router.callback_query(F.data.startswith("add_to_cart:"))
async def cb_add_to_cart(query: CallbackQuery, state: FSMContext):
    _, product_id_str, size = query.data.split(":")
    product_id = int(product_id_str)
    user_id = query.from_user.id

    if not await check_stock(product_id, size, 1):
        await query.answer("Sorry, that size is out of stock! 😔", show_alert=True)
        return

    cart = await add_item(user_id, product_id, size, 1)
    text = format_cart(cart)
    keyboard = cart_keyboard(cart.items)

    data = await state.get_data()
    cart_msg_id = data.get("cart_message_id")

    if cart_msg_id:
        try:
            await query.bot.edit_message_text(
                chat_id=query.message.chat.id,
                message_id=cart_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            await query.answer("Added to cart! 🛒")
            return
        except Exception:
            pass

    sent = await query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.update_data(cart_message_id=sent.message_id)
    await query.answer("Added to cart! 🛒")


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
    await query.answer("Quantity increased ➕")


@router.callback_query(F.data.startswith("cart_dec:"))
async def cb_cart_dec(query: CallbackQuery, state: FSMContext):
    item_id = int(query.data.split(":")[1])
    await update_item_quantity(item_id, query.from_user.id, -1)
    await _refresh_cart_message(query, state, query.from_user.id)
    await query.answer("Quantity decreased ➖")


@router.callback_query(F.data.startswith("cart_remove:"))
async def cb_cart_remove(query: CallbackQuery, state: FSMContext):
    item_id = int(query.data.split(":")[1])
    await remove_item(item_id, query.from_user.id)
    await _refresh_cart_message(query, state, query.from_user.id)
    await query.answer("Item removed ❌")


@router.callback_query(F.data == "cart_clear")
async def cb_cart_clear(query: CallbackQuery, state: FSMContext):
    await clear_cart(query.from_user.id)
    await query.message.edit_text("🛒 Your cart has been cleared.", reply_markup=None)
    await state.update_data(cart_message_id=None)
    await query.answer("Cart cleared!")


@router.callback_query(F.data == "checkout")
async def cb_checkout(query: CallbackQuery, state: FSMContext):
    from states.states import ShopStates
    cart = await get_or_create_cart(query.from_user.id)
    if not cart.items:
        await query.answer("Your cart is empty!", show_alert=True)
        return
    await state.set_state(ShopStates.collecting_name)
    await state.update_data(checkout_order_id=cart.id)
    await query.message.answer(
        "Let's get your order shipped! 📦\n\n"
        "Please enter your *full name* for the shipping label:",
        parse_mode="Markdown",
    )
    await query.answer()


@router.callback_query(F.data == "show_collection")
async def cb_show_collection(query: CallbackQuery):
    from config import settings
    from keyboards.keyboards import collection_keyboard
    keyboard = collection_keyboard(settings.SHOP_COLLECTION_URL)
    await query.message.answer("Here's our full collection! 🛍", reply_markup=keyboard)
    await query.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()
