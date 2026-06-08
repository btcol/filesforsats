"""
CRUD layer for filesforsats.
All DB interactions are isolated here so views_api stays clean.
"""

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    AdminSettings,
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


async def get_user_storage_usage(user_id: str) -> int:
    """Returns the total file size in bytes used by all products owned by user_id."""
    row = await db.fetchone(
        "SELECT SUM(file_size) as total FROM filesforsats.products WHERE user_id = :uid",
        {"uid": user_id},
    )
    return int(row["total"]) if row and row["total"] else 0


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


# ---------------------------------------------------------------------------
# Admin Settings CRUD
# ---------------------------------------------------------------------------


async def get_admin_settings() -> AdminSettings:
    """Return the single admin-settings row, creating it if it doesn't exist."""
    row = await db.fetchone(
        "SELECT * FROM filesforsats.admin_settings WHERE id = 1",
        {},
        AdminSettings,
    )
    if row is None:
        row = AdminSettings()
        await db.insert("filesforsats.admin_settings", row)
    return row


async def upsert_admin_settings(settings: AdminSettings) -> AdminSettings:
    """Overwrite the single admin-settings row."""
    await db.execute(
        """
        UPDATE filesforsats.admin_settings
           SET commission_percent     = :commission_percent,
               commission_wallet_id   = :commission_wallet_id,
               unlock_monthly         = :unlock_monthly
         WHERE id = 1
        """,
        {
            "commission_percent": settings.commission_percent,
            "commission_wallet_id": settings.commission_wallet_id,
            "unlock_monthly": settings.unlock_monthly,
        },
    )
    return settings


# ---------------------------------------------------------------------------
# Unlock Records CRUD — tracks when each user paid the unlock fee
# ---------------------------------------------------------------------------


async def upsert_unlock_record(user_id: str) -> None:
    """
    Record (or refresh) a successful unlock payment for *user_id*.
    Called each time the user pays the enable-invoice so the 30-day
    clock restarts on monthly renewals.
    """
    existing = await db.fetchone(
        "SELECT user_id FROM filesforsats.unlock_records WHERE user_id = :uid",
        {"uid": user_id},
    )
    if existing:
        await db.execute(
            """
            UPDATE filesforsats.unlock_records
               SET paid_at = CURRENT_TIMESTAMP,
                   active  = TRUE
             WHERE user_id = :uid
            """,
            {"uid": user_id},
        )
    else:
        await db.execute(
            """
            INSERT INTO filesforsats.unlock_records (user_id, active)
            VALUES (:uid, TRUE)
            """,
            {"uid": user_id},
        )


async def get_expired_unlock_records(cutoff_iso: str) -> list[dict]:
    """
    Return all unlock_records whose paid_at is older than *cutoff_iso*
    (ISO-8601 string, UTC) and are still marked active.
    Used by the monthly-expiry background task.
    """
    rows = await db.fetchall(
        """
        SELECT user_id, paid_at
          FROM filesforsats.unlock_records
         WHERE active = TRUE
           AND paid_at < :cutoff
        """,
        {"cutoff": cutoff_iso},
    )
    return [dict(r) for r in rows]


async def deactivate_unlock_record(user_id: str) -> None:
    """Mark a user's unlock as expired (active = FALSE)."""
    await db.execute(
        "UPDATE filesforsats.unlock_records SET active = FALSE WHERE user_id = :uid",
        {"uid": user_id},
    )
