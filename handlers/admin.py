import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from config import settings
from database.db import get_db, seed_products, SAMPLE_PRODUCTS
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


@router.message(Command("export_orders"))
async def cmd_export_orders(message: Message):
    """
    Admin-only command: /export_orders

    Manually triggers a full export of all submitted orders to the "Orders"
    tab of the configured export Google Sheet. Useful for initial population
    or re-syncing after a sheet is recreated.
    """
    if message.from_user.id != settings.ADMIN_CHAT_ID:
        await message.answer("⛔ Unauthorized.")
        return

    await message.answer("📤 Exporting all orders to Google Sheets…")

    from services.sheets_export_service import export_all_orders_to_sheet

    try:
        row_count = await export_all_orders_to_sheet()
        if row_count == 0:
            await message.answer(
                "⚠️ *Export completed with 0 rows.*\n\n"
                "_Either there are no submitted orders, or the export sheet is not configured. "
                "Check that `GOOGLE_SHEETS_EXPORT_ID` is set correctly._",
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                f"✅ *Orders exported successfully!*\n\n"
                f"📋 Rows written: *{row_count}*",
                parse_mode="Markdown",
            )
    except Exception as exc:
        logger.error(f"export_orders: Unexpected error: {exc}")
        await message.answer(
            f"❌ *Export failed.*\n\n`{exc}`",
            parse_mode="Markdown",
        )


@router.message(Command("export_inventory"))
async def cmd_export_inventory(message: Message):
    """
    Admin-only command: /export_inventory

    Manually triggers a full rewrite of the "Inventory" tab in the configured
    export Google Sheet with the current stock levels for all products.
    """
    if message.from_user.id != settings.ADMIN_CHAT_ID:
        await message.answer("⛔ Unauthorized.")
        return

    await message.answer("📤 Exporting current inventory to Google Sheets…")

    from services.sheets_export_service import update_inventory_sheet

    try:
        row_count = await update_inventory_sheet()
        if row_count == 0:
            await message.answer(
                "⚠️ *Export completed with 0 rows.*\n\n"
                "_Either there are no products, or the export sheet is not configured. "
                "Check that `GOOGLE_SHEETS_EXPORT_ID` is set correctly._",
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                f"✅ *Inventory exported successfully!*\n\n"
                f"📦 Products written: *{row_count}*",
                parse_mode="Markdown",
            )
    except Exception as exc:
        logger.error(f"export_inventory: Unexpected error: {exc}")
        await message.answer(
            f"❌ *Export failed.*\n\n`{exc}`",
            parse_mode="Markdown",
        )


@router.message(Command("refresh_products"))
async def cmd_refresh_products(message: Message):
    """
    Admin-only command: /refresh_products

    Fetches the latest product list from Google Sheets, clears the current
    products table, and reseeds it. Falls back to SAMPLE_PRODUCTS if the
    sheets fetch fails or returns nothing.

    Note: This deletes all rows from the products table. Existing orders that
    reference old product IDs will retain their product_id foreign keys, but
    the product details (name, price, etc.) will reflect the newly imported
    data. Avoid removing products that have open/pending orders.
    """
    if message.from_user.id != settings.ADMIN_CHAT_ID:
        await message.answer("⛔ Unauthorized.")
        return

    await message.answer("🔄 Refreshing product catalog from Google Sheets…")

    from services.sheets_service import fetch_products_from_sheets

    source = "Google Sheets"
    products: list[dict] = []

    try:
        products = await fetch_products_from_sheets()
        if not products:
            logger.info("refresh_products: Sheets returned no products — falling back to SAMPLE_PRODUCTS.")
            source = "SAMPLE_PRODUCTS (fallback — sheets empty or unconfigured)"
            products = SAMPLE_PRODUCTS
    except Exception as exc:
        logger.error(f"refresh_products: Sheets fetch failed: {exc}")
        source = f"SAMPLE_PRODUCTS (fallback — sheets error: {exc})"
        products = SAMPLE_PRODUCTS

    try:
        async with get_db() as conn:
            async with conn.transaction():
                # Remove existing products. We keep order_items intact so that
                # historical orders are not broken; the FK constraint is satisfied
                # as long as the same product IDs are re-inserted (which won't
                # happen with a full clear). For safety we only delete products
                # that are NOT referenced by any order_items.
                unreferenced = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM products
                    WHERE id NOT IN (SELECT DISTINCT product_id FROM order_items)
                    """
                )
                await conn.execute(
                    """
                    DELETE FROM products
                    WHERE id NOT IN (SELECT DISTINCT product_id FROM order_items)
                    """
                )
                await seed_products(conn, products)

        logger.info(
            f"refresh_products: Removed {unreferenced} unreferenced product(s), "
            f"inserted {len(products)} product(s) from {source}."
        )
        await message.answer(
            f"✅ *Product catalog refreshed!*\n\n"
            f"📦 Products imported: *{len(products)}*\n"
            f"🗂 Source: _{source}_\n\n"
            f"_Previously unreferenced products removed: {unreferenced}_",
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error(f"refresh_products: Database error during reseed: {exc}")
        await message.answer(
            f"❌ *Refresh failed during database update.*\n\n`{exc}`",
            parse_mode="Markdown",
        )
