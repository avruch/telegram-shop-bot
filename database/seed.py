"""
Run this script once to seed the database with sample products.
Usage: python database/seed.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
from config import settings

SAMPLE_PRODUCTS = [
    {
        "name": "R0001",
        "description": "",
        "price": 160,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/0b939078.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0002",
        "description": "",
        "price": 130,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/1655d32a.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0004",
        "description": "",
        "price": 150,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/f4e165d4.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0003",
        "description": "",
        "price": 200,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/65651711.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0005",
        "description": "",
        "price": 160,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/31c756c7.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0006",
        "description": "",
        "price": 130,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/8ca59476.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0007",
        "description": "",
        "price": 140,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/211667a2.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0008",
        "description": "",
        "price": 130,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/5d8eae8c.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R0009",
        "description": "",
        "price": 160,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/911f6909.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R010",
        "description": "",
        "price": 150,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/084488a8_original.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "R011",
        "description": "",
        "price": 200,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery02/a4b11990_original.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "G0001",
        "description": "",
        "price": 60,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/f3eecb51.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "G0002",
        "description": "",
        "price": 70,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/3efe7bb1.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "G0003",
        "description": "",
        "price": 60,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery03/9b23d93e.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "N0001",
        "description": "",
        "price": 50,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/2ccce319.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "N0002",
        "description": "",
        "price": 65,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/4446aa46.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
    {
        "name": "N0003",
        "description": "",
        "price": 100,
        "image_url": "https://ak94studio.carrd.co/assets/images/gallery01/da44ac0d.jpg?v=73a58a5a",
        "stock_json": json.dumps({"ONE SIZE": 10}),
    },
]


async def seed():
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        # Create tables if not exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image_url TEXT,
                stock_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Cart',
                total_price REAL NOT NULL DEFAULT 0.0,
                shipping_name TEXT,
                shipping_address TEXT,
                shipping_phone TEXT,
                screenshot_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # Clear existing products and re-seed
        await db.execute("DELETE FROM products")
        for product in SAMPLE_PRODUCTS:
            await db.execute(
                "INSERT INTO products (name, description, price, image_url, stock_json) VALUES (?, ?, ?, ?, ?)",
                (product["name"], product["description"], product["price"], product["image_url"], product["stock_json"]),
            )
        await db.commit()

    print(f"✅ Database seeded with {len(SAMPLE_PRODUCTS)} products at '{settings.DATABASE_PATH}'")
    print("\nProducts added:")
    for i, p in enumerate(SAMPLE_PRODUCTS, 1):
        print(f"  {i}. {p['name']} — ${p['price']}")


if __name__ == "__main__":
    asyncio.run(seed())
