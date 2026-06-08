"""
Background tasks for filesforsats:
  1. wait_for_paid_invoices  — marks purchases as paid when invoices settle.
  2. check_monthly_unlocks   — resets the pay-to-enable flag for users whose
                               30-day unlock window has expired (runs hourly).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from lnbits.core.models import Payment
from lnbits.core.models.extensions import UserExtension, UserExtensionInfo
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .crud import (
    deactivate_unlock_record,
    get_admin_settings,
    get_expired_unlock_records,
)
from .services import payment_received

_EXPIRY_CHECK_INTERVAL_SECONDS = 3600  # run every hour


async def wait_for_paid_invoices() -> None:
    invoice_queue: asyncio.Queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_filesforsats")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "filesforsats":
        return
    logger.info(f"filesforsats: invoice paid — hash={payment.payment_hash}")
    try:
        await payment_received(payment)
    except Exception as exc:
        logger.error(f"filesforsats: error processing payment: {exc}")


async def check_monthly_unlocks() -> None:
    """
    Periodic task: every hour, expire unlock records older than 30 days
    when the admin has enabled monthly-renewal mode.

    For each expired user:
    1. Sets unlock_records.active = FALSE (our DB).
    2. Sets UserExtension.extra.paid_to_enable = FALSE and active = FALSE
       in the LNbits core extensions table, forcing a fresh payment.
    """
    while True:
        await asyncio.sleep(_EXPIRY_CHECK_INTERVAL_SECONDS)
        try:
            await _run_expiry_check()
        except Exception as exc:
            logger.error(f"filesforsats monthly-unlock check error: {exc}")


async def _run_expiry_check() -> None:
    admin_cfg = await get_admin_settings()
    if not admin_cfg.unlock_monthly:
        return  # one-time mode — nothing to expire

    # 30 days ago in UTC, formatted as ISO-8601 for the SQL comparison
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cutoff_iso = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    expired = await get_expired_unlock_records(cutoff_iso)
    if not expired:
        return

    # Import LNbits core CRUD here (lazy) to avoid circular imports at module load
    from lnbits.core.crud.extensions import (  # type: ignore
        get_user_extension,
        update_user_extension,
    )

    logger.info(f"filesforsats: expiring {len(expired)} monthly unlock(s).")
    for record in expired:
        user_id: str = record["user_id"]
        try:
            # 1. Mark our record as inactive
            await deactivate_unlock_record(user_id)

            # 2. Reset the LNbits core extension state for this user
            user_ext: UserExtension | None = await get_user_extension(user_id, "filesforsats")
            if user_ext:
                user_ext.active = False
                user_ext.extra = UserExtensionInfo(
                    paid_to_enable=False,
                    payment_hash_to_enable=None,
                )
                await update_user_extension(user_ext)
                logger.info(f"filesforsats: monthly unlock expired for user {user_id}.")
        except Exception as exc:
            logger.error(f"filesforsats: failed to expire unlock for {user_id}: {exc}")
