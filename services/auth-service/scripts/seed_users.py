"""Create one user per role, for local testing.

Run from services/auth-service:
    python -m scripts.seed_users

Safe to run more than once: users that already exist are skipped.
"""

import asyncio

from app import user_repository
from app.core.database import close_db, connect_db
from app.core.permissions import Role
from app.core.security import hash_password
from app.models import new_user_document

SEED_PASSWORD = "Password123!"

SEED_USERS = [
    ("admin@example.com", "Admin User", Role.ADMIN),
    ("manager@example.com", "Inventory Manager", Role.INVENTORY_MANAGER),
    ("staff@example.com", "Warehouse Staff", Role.WAREHOUSE_STAFF),
    ("finance@example.com", "Finance Staff", Role.FINANCE_STAFF),
    ("viewer@example.com", "Viewer User", Role.VIEWER),
]


async def main() -> None:
    await connect_db()
    await user_repository.create_indexes()
    try:
        for email, full_name, role in SEED_USERS:
            if await user_repository.get_by_email(email):
                print(f"skip    {email} (already exists)")
                continue
            user_doc = new_user_document(email, hash_password(SEED_PASSWORD), full_name, role)
            await user_repository.create(user_doc)
            print(f"created {email} ({role})")
    finally:
        await close_db()
    print(f"\nAll seed users use the password: {SEED_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
