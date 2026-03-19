import re
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from states.states import ShopStates
from services.order_service import set_shipping_info, submit_for_payment, get_order, format_order_summary
from services.cart_service import get_or_create_cart, format_cart
from keyboards.keyboards import admin_confirm_keyboard
from config import settings
import texts

_PHONE_RE = re.compile(r'^\+?[\d\s\-\(\)]{7,20}$')

logger = logging.getLogger(__name__)
router = Router()


@router.message(ShopStates.collecting_name)
async def collect_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    # Must have at least two words (first + last name)
    if len(name.split()) < 2:
        await message.answer(texts.CHECKOUT_INVALID_NAME, parse_mode="Markdown")
        return
    await state.update_data(shipping_name=name)
    await state.set_state(ShopStates.collecting_address)
    await message.answer(texts.CHECKOUT_ASK_ADDRESS, parse_mode="Markdown")


@router.message(ShopStates.collecting_address)
async def collect_address(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    # Must be long enough and contain at least one digit (street number)
    has_digit = any(c.isdigit() for c in address)
    if len(address) < 10 or not has_digit:
        await message.answer(texts.CHECKOUT_INVALID_ADDRESS)
        return
    await state.update_data(shipping_address=address)
    await state.set_state(ShopStates.collecting_phone)
    await message.answer(texts.CHECKOUT_ASK_PHONE, parse_mode="Markdown")


@router.message(ShopStates.collecting_phone)
async def collect_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    if not _PHONE_RE.match(phone):
        await message.answer(texts.CHECKOUT_INVALID_PHONE, parse_mode="Markdown")
        return

    data = await state.get_data()
    shipping_name = data.get("shipping_name", "")
    shipping_address = data.get("shipping_address", "")
    shipping_phone = phone
    order_id = data.get("checkout_order_id")

    if not order_id:
        await message.answer(texts.CHECKOUT_NO_ORDER)
        await state.set_state(ShopStates.browsing)
        return

    await set_shipping_info(order_id, shipping_name, shipping_address, shipping_phone)

    order = await get_order(order_id)
    total = order.total_price if order else 0.0

    await state.update_data(shipping_phone=shipping_phone)
    await state.set_state(ShopStates.waiting_payment)

    await message.answer(
        texts.PAYMENT_INSTRUCTIONS.format(
            shipping_name=shipping_name,
            shipping_address=shipping_address,
            shipping_phone=shipping_phone,
            total=total,
            paypal_link=settings.PAYPAL_LINK,
        ),
        parse_mode="Markdown",
    )


@router.message(ShopStates.waiting_payment, F.photo)
async def receive_payment_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("checkout_order_id")

    if not order_id:
        await message.answer(texts.SCREENSHOT_ERROR)
        await state.clear()
        return

    photo = message.photo[-1]
    screenshot_file_id = photo.file_id

    await submit_for_payment(order_id, screenshot_file_id)

    order = await get_order(order_id)
    summary = format_order_summary(order) if order else f"Order #{order_id}"

    admin_keyboard = admin_confirm_keyboard(order_id, message.from_user.id)
    admin_text = texts.ADMIN_NEW_ORDER.format(
        order_id=order_id,
        summary=summary,
        username=message.from_user.username or "N/A",
        user_id=message.from_user.id,
    )

    try:
        await message.bot.send_photo(
            chat_id=settings.ADMIN_CHAT_ID,
            photo=screenshot_file_id,
            caption=admin_text,
            reply_markup=admin_keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

    await message.answer(texts.SCREENSHOT_RECEIVED, parse_mode="Markdown")
    await state.set_state(ShopStates.browsing)
    await state.update_data(checkout_order_id=None, cart_message_id=None)


@router.message(ShopStates.waiting_payment)
async def waiting_payment_non_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    total = 0.0
    if data.get("checkout_order_id"):
        from services.order_service import get_order as get_o
        o = await get_o(data["checkout_order_id"])
        if o:
            total = o.total_price

    await message.answer(
        texts.AWAITING_SCREENSHOT.format(total=total),
        parse_mode="Markdown",
    )
