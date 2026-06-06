# Migration file for the filesforsats extension.
# Rule: this file is like a blockchain — never edit, only add!

empty_dict: dict[str, str] = {}


async def m001_initial_products(db):
    """
    Creates the products table.
    Each product is a digital file the seller wants to sell.
    The sha256_hash is computed server-side on upload; never shared via API.
    """
    await db.execute(
        f"""
        CREATE TABLE filesforsats.products (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price_sats INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            storage_name TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            file_size INTEGER NOT NULL DEFAULT 0,
            sha256_hash TEXT NOT NULL,
            require_integrity BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m002_initial_purchases(db):
    """
    Creates the purchases table.
    A purchase tracks the payment lifecycle for a product sale.
    integrity_token is a one-time opaque UUID that proves
    the buyer passed the integrity check, required before invoice creation.
    """
    await db.execute(
        f"""
        CREATE TABLE filesforsats.purchases (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            payment_hash TEXT,
            payment_request TEXT,
            integrity_token TEXT,
            integrity_verified BOOLEAN NOT NULL DEFAULT FALSE,
            paid BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )