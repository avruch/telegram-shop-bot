import json
import logging
import asyncpg
from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

SAMPLE_PRODUCTS = [
    {"name": "R0001", "description": "", "price": 160, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/0b939078.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0002", "description": "", "price": 130, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/1655d32a.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0004", "description": "", "price": 150, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/f4e165d4.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0003", "description": "", "price": 200, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/65651711.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0005", "description": "", "price": 160, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/31c756c7.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0006", "description": "", "price": 130, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/8ca59476.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0007", "description": "", "price": 140, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/211667a2.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0008", "description": "", "price": 130, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/5d8eae8c.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R0009", "description": "", "price": 160, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/911f6909.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R010",  "description": "", "price": 150, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/084488a8_original.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "R011",  "description": "", "price": 200, "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/a4b11990_original.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "G0001", "description": "", "price": 60,  "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/f3eecb51.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "G0002", "description": "", "price": 70,  "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/3efe7bb1.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "G0003", "description": "", "price": 60,  "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/9b23d93e.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "N0001", "description": "", "price": 50,  "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/2ccce319.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "N0002", "description": "", "price": 65,  "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/4446aa46.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
    {"name": "N0003", "description": "", "price": 100, "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/da44ac0d.jpg?v=73a58a5a", "stock_json": json.dumps({"ONE SIZE": 10})},
]


def get_db():
    """Return a pool connection context manager: `async with get_db() as conn:`"""
    return _pool.acquire()


async def seed_products(conn: asyncpg.Connection, products: list[dict]) -> None:
    """Insert a list of product dicts into the products table."""
    await conn.executemany(
        "INSERT INTO products (name, description, price, image_url, stock_json) VALUES ($1, $2, $3, $4, $5)",
        [(p["name"], p["description"], p["price"], p["image_url"], p["stock_json"]) for p in products],
    )


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL)

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image_url TEXT,
                stock_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Cart',
                total_price REAL NOT NULL DEFAULT 0.0,
                shipping_name TEXT,
                shipping_address TEXT,
                shipping_phone TEXT,
                screenshot_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Auto-seed products if table is empty
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count == 0:
            # Try to seed from Google Sheets first; fall back to SAMPLE_PRODUCTS
            from services.sheets_service import fetch_products_from_sheets

            products_to_seed: list[dict] = []
            try:
                sheets_products = await fetch_products_from_sheets()
                if sheets_products:
                    products_to_seed = sheets_products
                    logger.info(
                        f"init_db: Seeding {len(products_to_seed)} product(s) from Google Sheets."
                    )
                else:
                    logger.info(
                        "init_db: Google Sheets returned no products — falling back to SAMPLE_PRODUCTS."
                    )
            except Exception as exc:
                logger.warning(
                    f"init_db: Failed to fetch from Google Sheets ({exc}) — "
                    "falling back to SAMPLE_PRODUCTS."
                )

            if not products_to_seed:
                products_to_seed = SAMPLE_PRODUCTS
                logger.info(
                    f"init_db: Seeding {len(products_to_seed)} product(s) from SAMPLE_PRODUCTS (fallback)."
                )

            await seed_products(conn, products_to_seed)
