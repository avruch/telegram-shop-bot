import logging
import aiohttp
from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from states.states import ShopStates
from services.ai_service import get_ai_response
from services.inventory_service import get_catalog_summary, get_product, check_stock
from services.cart_service import (
    get_or_create_cart,
    add_item,
    format_cart,
)
from keyboards.keyboards import product_size_keyboard, cart_keyboard, collection_keyboard
from config import settings
import texts

logger = logging.getLogger(__name__)
router = Router()


async def _send_product_card(message: Message, product_id: int):
    product = await get_product(product_id)
    if not product:
        await message.answer("Sorry, I couldn't find that product.")
        return
    caption = texts.PRODUCT_CAPTION.format(
        name=product.name,
        description=product.description,
        price=product.price,
    )
    keyboard = product_size_keyboard(product)
    if product.image_url:
        try:
            headers = {
                "Referer": "https://ak94studio.carrd.co/",
                "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(product.image_url) as resp:
                    resp.raise_for_status()
                    image_bytes = await resp.read()
            filename = product.image_url.split("/")[-1].split("?")[0] or "product.jpg"
            await message.answer_photo(
                BufferedInputFile(image_bytes, filename=filename),
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            return
        except Exception:
            logger.exception("Failed to send product image for product %s", product.id)
    await message.answer(caption, reply_markup=keyboard, parse_mode="Markdown")


async def _handle_action(message: Message, state: FSMContext, action: dict):
    action_name = action.get("action")
    user_id = message.from_user.id

    if action_name == "SHOW_PRODUCT":
        await _send_product_card(message, action.get("product_id"))

    elif action_name == "ADD_TO_CART":
        product_id = action.get("product_id")
        size = action.get("size", "").upper()
        quantity = int(action.get("quantity", 1))

        if not await check_stock(product_id, size, quantity):
            await _send_product_card(message, product_id)
            return

        cart = await add_item(user_id, product_id, size, quantity)
        text = format_cart(cart)
        data = await state.get_data()
        cart_msg_id = data.get("cart_message_id")
        keyboard = cart_keyboard(cart.items)

        if cart_msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=cart_msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                return
            except Exception:
                pass

        sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(cart_message_id=sent.message_id)

    elif action_name == "REMOVE_FROM_CART":
        from services.cart_service import remove_item
        order_item_id = action.get("order_item_id")
        cart = await remove_item(order_item_id, user_id)
        text = format_cart(cart)
        data = await state.get_data()
        cart_msg_id = data.get("cart_message_id")
        keyboard = cart_keyboard(cart.items) if cart.items else None

        if cart_msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=cart_msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    elif action_name == "SHOW_CART":
        cart = await get_or_create_cart(user_id)
        text = format_cart(cart)
        data = await state.get_data()
        cart_msg_id = data.get("cart_message_id")
        keyboard = cart_keyboard(cart.items) if cart.items else None

        if cart_msg_id and cart.items:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=cart_msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                return
            except Exception:
                pass
        sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        if cart.items:
            await state.update_data(cart_message_id=sent.message_id)

    elif action_name == "SHOW_COLLECTION":
        url = settings.SHOP_COLLECTION_URL
        keyboard = collection_keyboard(url)
        await message.answer(texts.COLLECTION_HEADER, reply_markup=keyboard)

    elif action_name == "START_CHECKOUT":
        cart = await get_or_create_cart(user_id)
        if not cart.items:
            await message.answer(texts.CART_EMPTY_CHECKOUT)
            return
        await state.set_state(ShopStates.collecting_name)
        await state.update_data(checkout_order_id=cart.id)
        await message.answer(texts.CHECKOUT_ASK_NAME, parse_mode="Markdown")


@router.message(ShopStates.browsing)
async def handle_chat(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(texts.TEXT_ONLY)
        return

    data = await state.get_data()
    history = data.get("conversation_history", [])
    catalog = await get_catalog_summary()
    cart = await get_or_create_cart(message.from_user.id)
    cart_summary = format_cart(cart)

    # Get AI response
    reply_text, actions = await get_ai_response(
        conversation_history=history,
        user_message=message.text,
        catalog=catalog,
        cart_summary=cart_summary,
    )

    # Update conversation history
    history.append({"role": "user", "parts": message.text})
    history.append({"role": "model", "parts": reply_text})
    if len(history) > 20:
        history = history[-20:]
    await state.update_data(conversation_history=history)

    # Send text reply
    if reply_text:
        await message.answer(reply_text, parse_mode="Markdown")

    # Execute actions
    for action in actions:
        await _handle_action(message, state, action)


@router.message(Command("checkout"))
async def cmd_checkout(message: Message, state: FSMContext):
    from services.cart_service import get_or_create_cart
    cart = await get_or_create_cart(message.from_user.id)
    if not cart.items:
        await message.answer(texts.CART_EMPTY_BROWSE)
        return
    await state.set_state(ShopStates.collecting_name)
    await state.update_data(checkout_order_id=cart.id)
    await message.answer(texts.CHECKOUT_START, parse_mode="Markdown")
