import json
from database.db import get_db
from database.models import Product


async def get_all_products() -> list[Product]:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM products") as cursor:
            rows = await cursor.fetchall()
        return [Product.from_row(row) for row in rows]
    finally:
        await db.close()


async def get_product(product_id: int) -> Product | None:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        return Product.from_row(row) if row else None
    finally:
        await db.close()


async def check_stock(product_id: int, size: str, quantity: int = 1) -> bool:
    # Made-to-order: no stock limits, just verify the product exists
    product = await get_product(product_id)
    return product is not None


async def deduct_stock(product_id: int, size: str, quantity: int) -> bool:
    """Deduct stock from a product. Returns True on success."""
    db = await get_db()
    try:
        async with db.execute("SELECT stock_json FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        stock = json.loads(row["stock_json"])
        if stock.get(size, 0) < quantity:
            return False
        stock[size] -= quantity
        await db.execute(
            "UPDATE products SET stock_json = ? WHERE id = ?",
            (json.dumps(stock), product_id),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def restore_stock(product_id: int, size: str, quantity: int):
    """Restore stock (e.g., when an order is rejected)."""
    db = await get_db()
    try:
        async with db.execute("SELECT stock_json FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        stock = json.loads(row["stock_json"])
        stock[size] = stock.get(size, 0) + quantity
        await db.execute(
            "UPDATE products SET stock_json = ? WHERE id = ?",
            (json.dumps(stock), product_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_catalog_summary() -> list[dict]:
    products = await get_all_products()
    return [p.to_catalog_summary() for p in products]
