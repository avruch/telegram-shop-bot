import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import settings
from services.order_service import confirm_payment, reject_payment, format_order_summary

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("admin_confirm:"))
async def cb_admin_confirm(query: CallbackQuery):
    if query.from_user.id != settings.ADMIN_CHAT_ID:
        await query.answer("Unauthorized.", show_alert=True)
        return

    _, order_id_str, user_id_str = query.data.split(":")
    order_id = int(order_id_str)
    user_id = int(user_id_str)

    order = await confirm_payment(order_id)
    if not order:
        await query.answer("Order not found.", show_alert=True)
        return

    # Notify customer
    try:
        await query.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 *Your payment has been confirmed!*\n\n"
                f"{format_order_summary(order)}\n\n"
                f"Your order is now being prepared for shipping. "
                f"Thank you for shopping with us! 💙"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify customer {user_id}: {e}")

    # Update admin message
    await query.message.edit_caption(
        caption=(
            f"✅ *Payment CONFIRMED — Order #{order_id}*\n\n"
            f"{format_order_summary(order)}\n\n"
            f"Customer notified."
        ),
        reply_markup=None,
        parse_mode="Markdown",
    )
    await query.answer("Payment confirmed! Customer notified. ✅")


@router.callback_query(F.data.startswith("admin_reject:"))
async def cb_admin_reject(query: CallbackQuery):
    if query.from_user.id != settings.ADMIN_CHAT_ID:
        await query.answer("Unauthorized.", show_alert=True)
        return

    _, order_id_str, user_id_str = query.data.split(":")
    order_id = int(order_id_str)
    user_id = int(user_id_str)

    order = await reject_payment(order_id)
    if not order:
        await query.answer("Order not found.", show_alert=True)
        return

    # Notify customer
    try:
        await query.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ *Payment Verification Failed — Order #{order_id}*\n\n"
                f"We were unable to verify your payment. This could be due to:\n"
                f"• Incorrect amount sent\n"
                f"• Screenshot not matching the transaction\n\n"
                f"Your cart has been restored. Please try again or contact support."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify customer {user_id}: {e}")

    # Update admin message
    await query.message.edit_caption(
        caption=f"❌ *Payment REJECTED — Order #{order_id}*\n\nStock restored. Customer notified.",
        reply_markup=None,
        parse_mode="Markdown",
    )
    await query.answer("Payment rejected. Customer notified. ❌")
