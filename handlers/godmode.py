import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings
from services.order_service import get_all_orders
from services.inventory_service import get_all_products

logger = logging.getLogger(__name__)
router = Router()

STATUS_EMOJI = {
    "Cart":    "🛒",
    "Pending": "⏳",
    "Paid":    "✅",
    "Rejected":"❌",
}


def _godmode_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 All Orders", callback_data="gm_orders"),
        InlineKeyboardButton(text="🛍 All Products", callback_data="gm_products"),
    )
    return builder.as_markup()


def _is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_CHAT_ID


@router.message(or_f(Command("godmode"), F.text.lower() == "godmode"))
async def cmd_godmode(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Unauthorized.")
        return
    await message.answer("🛠 *God Mode*\nWhat do you want to see?", reply_markup=_godmode_menu(), parse_mode="Markdown")


@router.callback_query(F.data == "gm_orders")
async def cb_gm_orders(query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("Unauthorized.", show_alert=True)
        return

    orders = await get_all_orders()
    if not orders:
        await query.message.edit_text("No orders yet.", reply_markup=_godmode_menu())
        return

    # Group by status
    grouped: dict[str, list] = {}
    for o in orders:
        grouped.setdefault(o.status, []).append(o)

    lines = ["📦 *All Orders*\n"]
    for status in ("Pending", "Paid", "Cart", "Rejected"):
        group = grouped.get(status, [])
        if not group:
            continue
        emoji = STATUS_EMOJI.get(status, "•")
        lines.append(f"{emoji} *{status}* ({len(group)})")
        for o in group:
            item_summary = ", ".join(
                f"{i.product_name or 'item'} ×{i.quantity} ({i.size})" for i in o.items
            ) or "—"
            lines.append(
                f"  Order #{o.id} | User `{o.user_id}` | ${o.total_price:.2f}\n"
                f"  _{item_summary}_"
            )
            if o.shipping_name:
                lines.append(f"  📬 {o.shipping_name} · {o.shipping_phone}")
        lines.append("")

    text = "\n".join(lines)
    # Telegram message limit is 4096 chars — split if needed
    if len(text) > 4000:
        text = text[:4000] + "\n…_(truncated)_"

    builder = InlineKeyboardBuilder()
    builder.button(text="« Back", callback_data="gm_menu")
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await query.answer()


@router.callback_query(F.data == "gm_products")
async def cb_gm_products(query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("Unauthorized.", show_alert=True)
        return

    products = await get_all_products()
    if not products:
        await query.message.edit_text("No products in database.", reply_markup=_godmode_menu())
        return

    lines = ["🛍 *All Products*\n"]
    for p in products:
        lines.append(
            f"*#{p.id} — {p.name}*\n"
            f"  💲 ${p.price:.2f}\n"
            f"  _{p.description[:60]}{'…' if len(p.description) > 60 else ''}_"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…_(truncated)_"

    builder = InlineKeyboardBuilder()
    builder.button(text="« Back", callback_data="gm_menu")
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await query.answer()


@router.callback_query(F.data == "gm_menu")
async def cb_gm_menu(query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("Unauthorized.", show_alert=True)
        return
    await query.message.edit_text("🛠 *God Mode*\nWhat do you want to see?", reply_markup=_godmode_menu(), parse_mode="Markdown")
    await query.answer()
