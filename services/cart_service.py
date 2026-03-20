from database.db import get_db
from database.models import Order, OrderItem
import texts


async def get_or_create_cart(user_id: int) -> Order:
    """Get the user's active Cart order, or create one."""
    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM orders WHERE user_id = $1 AND status = 'Cart'",
            user_id,
        )
        if row:
            order = Order.from_row(row)
        else:
            order_id = await conn.fetchval(
                "INSERT INTO orders (user_id, status, total_price) VALUES ($1, 'Cart', 0.0) RETURNING id",
                user_id,
            )
            order = Order(id=order_id, user_id=user_id, status="Cart", total_price=0.0)
        order.items = await _load_items(conn, order.id)
    return order


async def _load_items(conn, order_id: int) -> list[OrderItem]:
    rows = await conn.fetch(
        """SELECT oi.*, p.name, p.price
           FROM order_items oi
           JOIN products p ON oi.product_id = p.id
           WHERE oi.order_id = $1""",
        order_id,
    )
    return [OrderItem.from_row(r) for r in rows]


async def add_item(user_id: int, product_id: int, size: str, quantity: int = 1) -> Order:
    """Add an item to the cart. Merges with existing items of the same product+size."""
    cart = await get_or_create_cart(user_id)
    async with get_db() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT * FROM order_items WHERE order_id = $1 AND product_id = $2 AND size = $3",
                cart.id, product_id, size,
            )
            if existing:
                new_qty = existing["quantity"] + quantity
                await conn.execute(
                    "UPDATE order_items SET quantity = $1 WHERE id = $2",
                    new_qty, existing["id"],
                )
            else:
                await conn.execute(
                    "INSERT INTO order_items (order_id, product_id, size, quantity) VALUES ($1, $2, $3, $4)",
                    cart.id, product_id, size, quantity,
                )
            await _recalculate_total(conn, cart.id)
    return await get_or_create_cart(user_id)


async def remove_item(order_item_id: int, user_id: int) -> Order:
    async with get_db() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT oi.order_id FROM order_items oi JOIN orders o ON oi.order_id = o.id "
                "WHERE oi.id = $1 AND o.user_id = $2 AND o.status = 'Cart'",
                order_item_id, user_id,
            )
            if row:
                await conn.execute("DELETE FROM order_items WHERE id = $1", order_item_id)
                await _recalculate_total(conn, row["order_id"])
    return await get_or_create_cart(user_id)


async def update_item_quantity(order_item_id: int, user_id: int, delta: int) -> Order:
    """Increment or decrement item quantity by delta. Removes item if quantity reaches 0."""
    async with get_db() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT oi.*, o.id as order_id FROM order_items oi "
                "JOIN orders o ON oi.order_id = o.id "
                "WHERE oi.id = $1 AND o.user_id = $2 AND o.status = 'Cart'",
                order_item_id, user_id,
            )
            if row:
                new_qty = row["quantity"] + delta
                if new_qty <= 0:
                    await conn.execute("DELETE FROM order_items WHERE id = $1", order_item_id)
                else:
                    await conn.execute(
                        "UPDATE order_items SET quantity = $1 WHERE id = $2",
                        new_qty, order_item_id,
                    )
                await _recalculate_total(conn, row["order_id"])
    return await get_or_create_cart(user_id)


async def clear_cart(user_id: int) -> Order:
    cart = await get_or_create_cart(user_id)
    async with get_db() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM order_items WHERE order_id = $1", cart.id)
            await conn.execute("UPDATE orders SET total_price = 0.0 WHERE id = $1", cart.id)
    return await get_or_create_cart(user_id)


async def _recalculate_total(conn, order_id: int):
    total = await conn.fetchval(
        "SELECT SUM(oi.quantity * p.price) "
        "FROM order_items oi JOIN products p ON oi.product_id = p.id "
        "WHERE oi.order_id = $1",
        order_id,
    ) or 0.0
    await conn.execute("UPDATE orders SET total_price = $1 WHERE id = $2", total, order_id)


def format_cart(order: Order) -> str:
    if not order.items:
        return texts.CART_EMPTY
    lines = [texts.CART_HEADER]
    for item in order.items:
        name = item.product_name or f"Product #{item.product_id}"
        price = item.product_price or 0.0
        subtotal = price * item.quantity
        lines.append(texts.CART_ITEM_LINE.format(name=name, size=item.size, qty=item.quantity, subtotal=subtotal))
    lines.append(texts.CART_TOTAL_LINE.format(total=order.total_price))
    return "\n".join(lines)
