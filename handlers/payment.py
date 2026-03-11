import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from states.states import ShopStates
from services.order_service import set_shipping_info, submit_for_payment, get_order, format_order_summary
from services.cart_service import get_or_create_cart, format_cart
from keyboards.keyboards import admin_confirm_keyboard
from config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(ShopStates.collecting_name)
async def collect_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Please enter a valid full name.")
        return
    await state.update_data(shipping_name=message.text.strip())
    await state.set_state(ShopStates.collecting_address)
    await message.answer(
        "Got it! Now please enter your *shipping address*:\n"
        "_(Include street, city, state/province, and postal code)_",
        parse_mode="Markdown",
    )


@router.message(ShopStates.collecting_address)
async def collect_address(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("Please enter a valid shipping address.")
        return
    await state.update_data(shipping_address=message.text.strip())
    await state.set_state(ShopStates.collecting_phone)
    await message.answer(
        "Almost there! Please enter your *phone number*:\n"
        "_(Include country code, e.g. +1 555 123 4567)_",
        parse_mode="Markdown",
    )


@router.message(ShopStates.collecting_phone)
async def collect_phone(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 7:
        await message.answer("Please enter a valid phone number.")
        return

    data = await state.get_data()
    shipping_name = data.get("shipping_name", "")
    shipping_address = data.get("shipping_address", "")
    shipping_phone = message.text.strip()
    order_id = data.get("checkout_order_id")

    if not order_id:
        await message.answer("Something went wrong. Please start over with /checkout.")
        await state.set_state(ShopStates.browsing)
        return

    # Save shipping info to DB
    await set_shipping_info(order_id, shipping_name, shipping_address, shipping_phone)

    # Fetch order for total
    order = await get_order(order_id)
    total = order.total_price if order else 0.0

    await state.update_data(shipping_phone=shipping_phone)
    await state.set_state(ShopStates.waiting_payment)

    summary = (
        f"*Order Summary:*\n"
        f"📛 Name: {shipping_name}\n"
        f"📍 Address: {shipping_address}\n"
        f"📞 Phone: {shipping_phone}\n"
        f"💰 Total: *${total:.2f}*"
    )

    await message.answer(
        f"{summary}\n\n"
        f"*Payment Instructions:*\n"
        f"Please send *${total:.2f}* to our PayPal:\n"
        f"👉 {settings.PAYPAL_LINK}\n\n"
        f"After completing your payment, please upload a *screenshot* of the transaction here. "
        f"We'll confirm your order as soon as we verify it! ✅",
        parse_mode="Markdown",
    )


@router.message(ShopStates.waiting_payment, F.photo)
async def receive_payment_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("checkout_order_id")

    if not order_id:
        await message.answer("Something went wrong. Please start over with /start.")
        await state.clear()
        return

    # Use the largest photo (best quality)
    photo = message.photo[-1]
    screenshot_file_id = photo.file_id

    # Update order to Pending, deduct stock
    await submit_for_payment(order_id, screenshot_file_id)

    order = await get_order(order_id)
    summary = format_order_summary(order) if order else f"Order #{order_id}"

    # Notify admin
    admin_keyboard = admin_confirm_keyboard(order_id, message.from_user.id)
    admin_text = (
        f"🔔 *New Payment Pending — Order #{order_id}*\n\n"
        f"{summary}\n\n"
        f"👤 Customer: @{message.from_user.username or 'N/A'} "
        f"(ID: `{message.from_user.id}`)\n\n"
        f"Please verify the screenshot below and confirm or reject:"
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

    # Confirm to user
    await message.answer(
        "✅ *Payment screenshot received!*\n\n"
        "Your order is now under review. We'll notify you once your payment is confirmed. "
        "This usually takes a few minutes. Thank you! 🙏",
        parse_mode="Markdown",
    )
    await state.set_state(ShopStates.browsing)
    await state.update_data(checkout_order_id=None, cart_message_id=None)


@router.message(ShopStates.waiting_payment)
async def waiting_payment_non_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    order = await get_or_create_cart(message.from_user.id)
    total = 0.0
    if data.get("checkout_order_id"):
        from services.order_service import get_order as get_o
        o = await get_o(data["checkout_order_id"])
        if o:
            total = o.total_price

    await message.answer(
        f"Please upload a *screenshot* of your PayPal payment (${total:.2f}) to confirm your order.\n"
        f"Send it as an image/photo. 📸",
        parse_mode="Markdown",
    )
