"""
Background task: listens for paid invoices and marks purchases as paid.
"""

import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .services import payment_received


async def wait_for_paid_invoices():
    invoice_queue: asyncio.Queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_filesforsats")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "filesforsats":
        return
    logger.info(f"files4sats: invoice paid — hash={payment.payment_hash}")
    try:
        await payment_received(payment)
    except Exception as exc:
        logger.error(f"files4sats: error processing payment: {exc}")