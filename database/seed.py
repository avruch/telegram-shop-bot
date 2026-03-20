"""
Run this script once to seed the database with sample products.
Usage: python database/seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, SAMPLE_PRODUCTS
from config import settings


async def seed():
    # init_db creates tables and auto-seeds if empty.
    # To force a re-seed, we connect directly and clear first.
    import asyncpg
    pool = await asyncpg.create_pool(settings.DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM order_items")
        await conn.execute("DELETE FROM products")
        await conn.executemany(
            "INSERT INTO products (name, description, price, image_url, stock_json) VALUES ($1, $2, $3, $4, $5)",
            [(p["name"], p["description"], p["price"], p["image_url"], p["stock_json"]) for p in SAMPLE_PRODUCTS],
        )
    await pool.close()
    print(f"✅ Database seeded with {len(SAMPLE_PRODUCTS)} products")
    print("\nProducts added:")
    for i, p in enumerate(SAMPLE_PRODUCTS, 1):
        print(f"  {i}. {p['name']} — ${p['price']}")


if __name__ == "__main__":
    asyncio.run(seed())
