from database.db import get_db
from database.models import Order, OrderItem
from services.inventory_service import deduct_stock, restore_stock


async def get_order(order_id: int) -> Order | None:
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not row:
            return None
        order = Order.from_row(row)
        item_rows = await conn.fetch(
            "SELECT oi.*, p.name, p.price FROM order_items oi "
            "JOIN products p ON oi.product_id = p.id WHERE oi.order_id = $1",
            order_id,
        )
        order.items = [OrderItem.from_row(r) for r in item_rows]
    return order


async def get_user_cart_order(user_id: int) -> Order | None:
    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM orders WHERE user_id = $1 AND status = 'Cart'", user_id
        )
        if not row:
            return None
        order = Order.from_row(row)
        item_rows = await conn.fetch(
            "SELECT oi.*, p.name, p.price FROM order_items oi "
            "JOIN products p ON oi.product_id = p.id WHERE oi.order_id = $1",
            order.id,
        )
        order.items = [OrderItem.from_row(r) for r in item_rows]
    return order


async def set_shipping_info(order_id: int, name: str, address: str, phone: str):
    async with get_db() as conn:
        await conn.execute(
            "UPDATE orders SET shipping_name = $1, shipping_address = $2, shipping_phone = $3 WHERE id = $4",
            name, address, phone, order_id,
        )


async def submit_for_payment(order_id: int, screenshot_file_id: str):
    """Move order to Pending, save screenshot, deduct stock temporarily."""
    order = await get_order(order_id)
    if not order:
        return

    async with get_db() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'Pending', screenshot_file_id = $1 WHERE id = $2",
            screenshot_file_id, order_id,
        )

    for item in order.items:
        await deduct_stock(item.product_id, item.size, item.quantity)


async def confirm_payment(order_id: int) -> Order | None:
    """Mark order as Paid."""
    async with get_db() as conn:
        await conn.execute("UPDATE orders SET status = 'Paid' WHERE id = $1", order_id)
    return await get_order(order_id)


async def reject_payment(order_id: int) -> Order | None:
    """Reject payment: restore stock and reset order to Cart."""
    order = await get_order(order_id)
    if not order:
        return None

    for item in order.items:
        await restore_stock(item.product_id, item.size, item.quantity)

    async with get_db() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'Cart', screenshot_file_id = NULL WHERE id = $1",
            order_id,
        )
    return await get_order(order_id)


async def get_all_orders() -> list[Order]:
    async with get_db() as conn:
        rows = await conn.fetch("SELECT * FROM orders ORDER BY id DESC")
        orders = []
        for row in rows:
            order = Order.from_row(row)
            item_rows = await conn.fetch(
                "SELECT oi.*, p.name, p.price FROM order_items oi "
                "JOIN products p ON oi.product_id = p.id WHERE oi.order_id = $1",
                order.id,
            )
            order.items = [OrderItem.from_row(r) for r in item_rows]
            orders.append(order)
    return orders


def format_order_summary(order: Order) -> str:
    lines = [f"📦 *Order #{order.id}*\n"]
    for item in order.items:
        name = item.product_name or f"Product #{item.product_id}"
        price = item.product_price or 0.0
        lines.append(f"• {name} ({item.size}) × {item.quantity} — ${price * item.quantity:.2f}")
    lines.append(f"\n💰 *Total: ${order.total_price:.2f}*")
    if order.shipping_name:
        lines.append(f"\n📬 *Shipping Details:*")
        lines.append(f"  Name: {order.shipping_name}")
        lines.append(f"  Address: {order.shipping_address}")
        lines.append(f"  Phone: {order.shipping_phone}")
    return "\n".join(lines)
