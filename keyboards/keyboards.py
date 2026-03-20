from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import Product, Order, OrderItem


def product_size_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Inline keyboard for a product card — size is collected via chat."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛒 Add to Cart", callback_data=f"want_product:{product.id}"),
    )
    builder.row(
        InlineKeyboardButton(text="👜 View Cart", callback_data="show_cart"),
        InlineKeyboardButton(text="📦 All Products", callback_data="show_collection"),
    )
    return builder.as_markup()


def cart_keyboard(items: list[OrderItem]) -> InlineKeyboardMarkup:
    """Live cart keyboard with ➕ ➖ ❌ buttons per item."""
    builder = InlineKeyboardBuilder()
    for item in items:
        name = item.product_name or f"Product #{item.product_id}"
        builder.row(
            InlineKeyboardButton(text=f"➖", callback_data=f"cart_dec:{item.id}"),
            InlineKeyboardButton(
                text=f"{item.quantity}x {name} ({item.size})",
                callback_data="noop",
            ),
            InlineKeyboardButton(text=f"➕", callback_data=f"cart_inc:{item.id}"),
            InlineKeyboardButton(text="❌", callback_data=f"cart_remove:{item.id}"),
        )
    builder.row(
        InlineKeyboardButton(text="✅ Checkout", callback_data="checkout"),
    )
    return builder.as_markup()


def admin_confirm_keyboard(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard to confirm or reject a payment."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Confirm Payment",
            callback_data=f"admin_confirm:{order_id}:{user_id}",
        ),
        InlineKeyboardButton(
            text="❌ Reject",
            callback_data=f"admin_reject:{order_id}:{user_id}",
        ),
    )
    return builder.as_markup()


def collection_keyboard(url: str) -> InlineKeyboardMarkup:
    """Button to open the full product collection."""
    builder = InlineKeyboardBuilder()
    if url:
        builder.button(text="🛍 Browse Full Collection", url=url)
    builder.button(text="🛒 My Cart", callback_data="show_cart")
    builder.adjust(1)
    return builder.as_markup()
