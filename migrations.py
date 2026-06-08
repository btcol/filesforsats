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


async def m003_admin_settings(db):
    """
    Creates a single-row table for extension-level admin settings.
    - commission_percent: percentage (0-100) deducted from each sale and
      forwarded to commission_wallet_id.
    - commission_wallet_id: LNbits wallet that receives the commission.
    - unlock_monthly: if TRUE, the pay-to-enable fee must be paid every
      calendar month; if FALSE it is a one-time lifetime payment (default).
    """
    await db.execute(
        """
        CREATE TABLE filesforsats.admin_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            commission_percent REAL NOT NULL DEFAULT 0,
            commission_wallet_id TEXT NOT NULL DEFAULT '',
            unlock_monthly BOOLEAN NOT NULL DEFAULT FALSE
        );
    """
    )
    # Seed the single row so GET always returns a result.
    await db.execute("INSERT INTO filesforsats.admin_settings (id) VALUES (1);")


async def m004_unlock_records(db):
    """
    Tracks when each user paid the extension unlock fee.
    Used by the monthly-expiry background task to reset paid_to_enable
    for users whose unlock is older than 30 days when unlock_monthly = TRUE.

    paid_at  — UTC timestamp of the most recent successful unlock payment.
    active   — TRUE while the unlock is still valid; set to FALSE by the
               expiry task when unlock_monthly is enabled and 30 days pass.
    """
    await db.execute(
        f"""
        CREATE TABLE filesforsats.unlock_records (
            user_id  TEXT PRIMARY KEY,
            paid_at  TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            active   BOOLEAN NOT NULL DEFAULT TRUE
        );
    """
    )


async def m005_admin_settings_storage_quota(db):
    """
    Adds storage_quota_mb to admin_settings to configure max storage per user.
    """
    await db.execute(
        "ALTER TABLE filesforsats.admin_settings ADD COLUMN storage_quota_mb INTEGER NOT NULL DEFAULT 1024;"
    )


async def m006_add_currency_columns(db):
    """
    Adds multi-currency support to products.
    - price: the product price in the chosen currency (replaces the integer-only price_sats).
    - currency: ISO 4217 code or 'sat' / 'btc' (default: 'sat').
    - default_currency on admin_settings: pre-selected currency for new products.

    Existing rows keep price_sats; price is back-filled from price_sats so that
    sat-priced products continue to work without data loss.
    """
    await db.execute(
        "ALTER TABLE filesforsats.products ADD COLUMN price REAL NOT NULL DEFAULT 0;"
    )
    await db.execute(
        "ALTER TABLE filesforsats.products ADD COLUMN currency TEXT NOT NULL DEFAULT 'sat';"
    )
    # Back-fill price from the legacy integer column so existing products work
    await db.execute(
        "UPDATE filesforsats.products SET price = CAST(price_sats AS REAL) WHERE price = 0;"
    )
    await db.execute(
        "ALTER TABLE filesforsats.admin_settings ADD COLUMN default_currency TEXT NOT NULL DEFAULT 'sat';"
    )
