"""
CRUD layer for files4sats.
All DB interactions are isolated here so views_api stays clean.
"""

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    Product,
    ProductFilters,
    Purchase,
)

db = Database("ext_filesforsats")


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------


async def create_product(product: Product) -> Product:
    await db.insert("filesforsats.products", product)
    return product


async def get_product(product_id: str) -> Product | None:
    return await db.fetchone(
        "SELECT * FROM filesforsats.products WHERE id = :id",
        {"id": product_id},
        Product,
    )


async def get_product_owned(user_id: str, product_id: str) -> Product | None:
    return await db.fetchone(
        "SELECT * FROM filesforsats.products WHERE id = :id AND user_id = :user_id",
        {"id": product_id, "user_id": user_id},
        Product,
    )


async def get_products_paginated(
    user_id: str | None = None,
    filters: Filters[ProductFilters] | None = None,
) -> Page[Product]:
    where = []
    values = {}
    if user_id:
        where.append("user_id = :user_id")
        values["user_id"] = user_id
    return await db.fetch_page(
        "SELECT * FROM filesforsats.products",
        where=where,
        values=values,
        filters=filters,
        model=Product,
    )


async def update_product(product: Product) -> Product:
    await db.update("filesforsats.products", product)
    return product


async def delete_product(user_id: str, product_id: str) -> None:
    await db.execute(
        "DELETE FROM filesforsats.products WHERE id = :id AND user_id = :user_id",
        {"id": product_id, "user_id": user_id},
    )


# ---------------------------------------------------------------------------
# Purchase CRUD
# ---------------------------------------------------------------------------


async def create_purchase(purchase: Purchase) -> Purchase:
    await db.insert("filesforsats.purchases", purchase)
    return purchase


async def get_purchase(purchase_id: str) -> Purchase | None:
    return await db.fetchone(
        "SELECT * FROM filesforsats.purchases WHERE id = :id",
        {"id": purchase_id},
        Purchase,
    )


async def get_purchase_by_payment_hash(payment_hash: str) -> Purchase | None:
    return await db.fetchone(
        "SELECT * FROM filesforsats.purchases WHERE payment_hash = :payment_hash",
        {"payment_hash": payment_hash},
        Purchase,
    )


async def get_purchase_by_integrity_token(token: str) -> Purchase | None:
    return await db.fetchone(
        "SELECT * FROM filesforsats.purchases WHERE integrity_token = :token",
        {"token": token},
        Purchase,
    )


async def update_purchase(purchase: Purchase) -> Purchase:
    await db.update("filesforsats.purchases", purchase)
    return purchase
