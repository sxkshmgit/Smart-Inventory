"""MongoDB connection: one shared client for the whole app."""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings

# Created once at startup and reused by every request.
# A MongoDB client keeps a pool of connections, so we don't open one per request.
client: AsyncMongoClient | None = None


async def connect_db() -> None:

    global client
    # tz_aware=True: dates read back from MongoDB keep their UTC timezone.
    client = AsyncMongoClient(settings.MONGO_URI, tz_aware=True)
    # "ping" fails fast if the URI, password or network access is wrong.
    await client.admin.command("ping")


async def close_db() -> None:
    if client is not None:
        await client.close()


def get_db() -> AsyncDatabase:
    """Return the app's database. Used by the repositories."""
    if client is None:
        raise RuntimeError("Database is not connected. Was connect_db() called?")
    return client[settings.DB_NAME]
