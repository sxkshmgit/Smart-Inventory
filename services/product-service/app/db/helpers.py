"""Shape of products and categories as stored in MongoDB, and how they are turned into API output."""

from datetime import datetime, timezone


def new_product_document(fields: dict, sku: str, created_by: str) -> dict:
    """Build a new product document. `fields` are the validated values from ProductCreate."""
    now = datetime.now(timezone.utc)
    return {
        **fields,
        "sku": sku,
        "status": "active",
        "created_by": created_by,
        "updated_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def product_to_out(doc: dict) -> dict:
    """Pick the fields the API returns (whitelist), turning _id into a string id."""
    return {
        "id": str(doc["_id"]),
        "sku": doc["sku"],
        "name": doc["name"],
        "description": doc.get("description"),
        "category": doc["category"],
        "brand": doc.get("brand"),
        "supplier_ids": doc.get("supplier_ids", []),
        "cost_price": doc["cost_price"],
        "selling_price": doc["selling_price"],
        "reorder_level": doc.get("reorder_level", 0),
        "tax_percentage": doc.get("tax_percentage", 0),
        "unit": doc.get("unit", "pcs"),
        "images": doc.get("images", []),
        "status": doc["status"],
        "created_by": doc["created_by"],
        "updated_by": doc["updated_by"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


def new_category_document(name: str, parent_id: str | None, created_by: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "name": name,
        # Lower-case copy for the unique index: "Electronics" and "electronics" count as the same.
        "name_lower": name.lower(),
        "parent_id": parent_id,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def category_to_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "parent_id": doc.get("parent_id"),
        "created_by": doc["created_by"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }
