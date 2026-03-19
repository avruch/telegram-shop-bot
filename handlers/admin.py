import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import settings
from services.order_service import confirm_payment, reject_payment, format_order_summary
import texts

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

    try:
        await query.bot.send_message(
            chat_id=user_id,
            text=texts.CUSTOMER_ORDER_CONFIRMED.format(summary=format_order_summary(order)),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify customer {user_id}: {e}")

    await query.message.edit_caption(
        caption=texts.ADMIN_CONFIRMED.format(order_id=order_id, summary=format_order_summary(order)),
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

    try:
        await query.bot.send_message(
            chat_id=user_id,
            text=texts.CUSTOMER_ORDER_REJECTED.format(order_id=order_id),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify customer {user_id}: {e}")

    await query.message.edit_caption(
        caption=texts.ADMIN_REJECTED.format(order_id=order_id),
        reply_markup=None,
        parse_mode="Markdown",
    )
    await query.answer("Payment rejected. Customer notified. ❌")
