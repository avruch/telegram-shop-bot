from database.db import get_db
from database.models import Order, OrderItem


async def get_or_create_cart(user_id: int) -> Order:
    """Get the user's active Cart order, or create one."""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status = 'Cart'",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            order = Order.from_row(row)
        else:
            async with db.execute(
                "INSERT INTO orders (user_id, status, total_price) VALUES (?, 'Cart', 0.0)",
                (user_id,),
            ) as cursor:
                order_id = cursor.lastrowid
            await db.commit()
            order = Order(id=order_id, user_id=user_id, status="Cart", total_price=0.0)
        order.items = await _load_items(db, order.id)
        return order
    finally:
        await db.close()


async def _load_items(db, order_id: int) -> list[OrderItem]:
    async with db.execute(
        """SELECT oi.*, p.name, p.price
           FROM order_items oi
           JOIN products p ON oi.product_id = p.id
           WHERE oi.order_id = ?""",
        (order_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [OrderItem.from_row(r) for r in rows]


async def add_item(user_id: int, product_id: int, size: str, quantity: int = 1) -> Order:
    """Add an item to the cart. Merges with existing items of the same product+size."""
    cart = await get_or_create_cart(user_id)
    db = await get_db()
    try:
        # Check if item already in cart
        async with db.execute(
            "SELECT * FROM order_items WHERE order_id = ? AND product_id = ? AND size = ?",
            (cart.id, product_id, size),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            new_qty = existing["quantity"] + quantity
            await db.execute(
                "UPDATE order_items SET quantity = ? WHERE id = ?",
                (new_qty, existing["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO order_items (order_id, product_id, size, quantity) VALUES (?, ?, ?, ?)",
                (cart.id, product_id, size, quantity),
            )

        await _recalculate_total(db, cart.id)
        await db.commit()
    finally:
        await db.close()

    return await get_or_create_cart(user_id)


async def remove_item(order_item_id: int, user_id: int) -> Order:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT oi.order_id FROM order_items oi JOIN orders o ON oi.order_id = o.id "
            "WHERE oi.id = ? AND o.user_id = ? AND o.status = 'Cart'",
            (order_item_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            await db.execute("DELETE FROM order_items WHERE id = ?", (order_item_id,))
            await _recalculate_total(db, row["order_id"])
            await db.commit()
    finally:
        await db.close()
    return await get_or_create_cart(user_id)


async def update_item_quantity(order_item_id: int, user_id: int, delta: int) -> Order:
    """Increment or decrement item quantity by delta. Removes item if quantity reaches 0."""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT oi.*, o.id as order_id FROM order_items oi "
            "JOIN orders o ON oi.order_id = o.id "
            "WHERE oi.id = ? AND o.user_id = ? AND o.status = 'Cart'",
            (order_item_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            new_qty = row["quantity"] + delta
            if new_qty <= 0:
                await db.execute("DELETE FROM order_items WHERE id = ?", (order_item_id,))
            else:
                await db.execute(
                    "UPDATE order_items SET quantity = ? WHERE id = ?",
                    (new_qty, order_item_id),
                )
            await _recalculate_total(db, row["order_id"])
            await db.commit()
    finally:
        await db.close()
    return await get_or_create_cart(user_id)


async def clear_cart(user_id: int) -> Order:
    cart = await get_or_create_cart(user_id)
    db = await get_db()
    try:
        await db.execute("DELETE FROM order_items WHERE order_id = ?", (cart.id,))
        await db.execute("UPDATE orders SET total_price = 0.0 WHERE id = ?", (cart.id,))
        await db.commit()
    finally:
        await db.close()
    return await get_or_create_cart(user_id)


async def _recalculate_total(db, order_id: int):
    async with db.execute(
        "SELECT SUM(oi.quantity * p.price) as total "
        "FROM order_items oi JOIN products p ON oi.product_id = p.id "
        "WHERE oi.order_id = ?",
        (order_id,),
    ) as cursor:
        row = await cursor.fetchone()
    total = row["total"] or 0.0
    await db.execute("UPDATE orders SET total_price = ? WHERE id = ?", (total, order_id))


def format_cart(order: Order) -> str:
    if not order.items:
        return "🛒 Your cart is empty."
    lines = ["🛒 *Your Cart:*\n"]
    for item in order.items:
        name = item.product_name or f"Product #{item.product_id}"
        price = item.product_price or 0.0
        subtotal = price * item.quantity
        lines.append(f"• {name} ({item.size}) × {item.quantity} — ${subtotal:.2f}")
    lines.append(f"\n💰 *Total: ${order.total_price:.2f}*")
    return "\n".join(lines)
