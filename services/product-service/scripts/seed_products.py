"""Create demo categories and products, for local testing.

Run from services/product-service:
    python -m scripts.seed_products

Safe to run more than once: categories and products that already exist are skipped.
"""

import asyncio
from decimal import Decimal

from app.core.database import close_db, connect_db
from app.db import db_queries
from app.db.model import Category, Product
from app.routes.products import sku_prefix

SEED_BY = "seed"

CATEGORIES = ["Electronics", "Grocery", "Clothing"]

# (category, name, brand, cost_price, selling_price, tax %, unit, reorder level)
PRODUCTS = [
    ("Electronics", "iPhone 15", "Apple", "60000.00", "79900.00", 18, "pcs", 5),
    ("Electronics", "Samsung Galaxy S24", "Samsung", "55000.00", "74999.00", 18, "pcs", 5),
    ("Electronics", "MacBook Air M3", "Apple", "90000.00", "114900.00", 18, "pcs", 3),
    ("Electronics", "Dell Inspiron 15", "Dell", "45000.00", "58990.00", 18, "pcs", 3),
    ("Grocery", "Basmati Rice 5kg", "India Gate", "400.00", "550.00", 5, "bag", 20),
    ("Grocery", "Toor Dal 1kg", "Tata Sampann", "120.00", "165.00", 5, "kg", 30),
    ("Grocery", "Tata Tea Gold 500g", "Tata", "220.00", "290.00", 5, "box", 25),
    ("Grocery", "Coca-Cola 2L", "Coca-Cola", "70.00", "95.00", 12, "bottle", 50),
    ("Clothing", "Cotton T-Shirt", "Roadster", "250.00", "499.00", 12, "pcs", 15),
    ("Clothing", "Denim Jeans", "Levi's", "600.00", "1299.00", 12, "pcs", 10),
]


async def get_or_create_category(name: str) -> Category:
    """Return the category, creating it only if it doesn't exist yet."""
    existing = await db_queries.get_category_by_name(name)
    if existing:
        print(f"skip    category {name}")
        return existing
    category = await db_queries.create_category(Category(name=name, created_by=SEED_BY))
    print(f"created category {name}")
    return category


async def main() -> None:
    await connect_db()
    await db_queries.create_indexes()
    try:
        # 1. Categories first: every product needs one.
        categories = {name: await get_or_create_category(name) for name in CATEGORIES}

        # 2. Products, with a SKU made the same way as POST /products.
        for category_name, name, brand, cost, selling, tax, unit, reorder in PRODUCTS:
            if await db_queries.get_product_by_name(name):
                print(f"skip    product  {name}")
                continue
            category = categories[category_name]
            prefix = sku_prefix(category.name)
            sku = f"{prefix}-{await db_queries.next_sequence(prefix):06d}"
            product = Product(
                sku=sku,
                name=name,
                category_id=category.id,
                category_name=category.name,
                brand=brand,
                cost_price=Decimal(cost),
                selling_price=Decimal(selling),
                tax_percentage=tax,
                unit=unit,
                reorder_level=reorder,
                created_by=SEED_BY,
                updated_by=SEED_BY,
            )
            await db_queries.create(product)
            print(f"created product  {name} ({sku})")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
