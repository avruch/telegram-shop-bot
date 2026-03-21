import json
import logging
from database.db import get_db
from database.models import Product

logger = logging.getLogger(__name__)


async def get_all_products() -> list[Product]:
    async with get_db() as conn:
        rows = await conn.fetch("SELECT * FROM products")
    return [Product.from_row(row) for row in rows]


async def get_product(product_id: int) -> Product | None:
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    return Product.from_row(row) if row else None


async def check_stock(product_id: int, size: str, quantity: int = 1) -> bool:
    # Made-to-order: no stock limits, just verify the product exists
    product = await get_product(product_id)
    return product is not None


async def deduct_stock(product_id: int, size: str, quantity: int) -> bool:
    """Deduct stock from a product. Returns True on success."""
    async with get_db() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT stock_json FROM products WHERE id = $1", product_id)
            if not row:
                return False
            stock = json.loads(row["stock_json"])
            if stock.get(size, 0) < quantity:
                return False
            stock[size] -= quantity
            await conn.execute(
                "UPDATE products SET stock_json = $1 WHERE id = $2",
                json.dumps(stock), product_id,
            )

    try:
        import services.sheets_export_service as sheets_export
        await sheets_export.update_inventory_sheet()
    except Exception as exc:
        logger.error(f"inventory_service: sheets inventory export failed after deduct_stock: {exc}")

    return True


async def restore_stock(product_id: int, size: str, quantity: int):
    """Restore stock (e.g., when an order is rejected)."""
    async with get_db() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT stock_json FROM products WHERE id = $1", product_id)
            if not row:
                return
            stock = json.loads(row["stock_json"])
            stock[size] = stock.get(size, 0) + quantity
            await conn.execute(
                "UPDATE products SET stock_json = $1 WHERE id = $2",
                json.dumps(stock), product_id,
            )

    try:
        import services.sheets_export_service as sheets_export
        await sheets_export.update_inventory_sheet()
    except Exception as exc:
        logger.error(f"inventory_service: sheets inventory export failed after restore_stock: {exc}")


async def get_catalog_summary() -> list[dict]:
    products = await get_all_products()
    return [p.to_catalog_summary() for p in products]
