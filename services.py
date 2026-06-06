"""
Business-logic / service layer for files4sats.

Key responsibilities:
- Compute SHA-256 of uploaded files (server-side only)
- Validate buyer integrity codes without leaking the expected hash
- Create LNbits invoices for verified purchases
- Mark purchases as paid when the invoice webhook fires
"""

import hashlib
import mimetypes
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from http import HTTPStatus
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.helpers import urlsafe_short_hash
from loguru import logger

from .crud import (
    create_purchase,
    get_product,
    get_purchase_by_integrity_token,
    get_purchase_by_payment_hash,
    update_purchase,
)
from .models import (
    InvoiceResponse,
    Product,
    Purchase,
    VerifyIntegrityResponse,
)

# ---------------------------------------------------------------------------
# Configuration — adjust here; never hardcode elsewhere
# ---------------------------------------------------------------------------

#: Maximum allowed upload size in bytes.  1 GiB default — change freely.
MAX_UPLOAD_BYTES: int = 1 * 1024 * 1024 * 1024  # 1 GiB

#: File types that are explicitly blocked regardless of extension.
BLOCKED_MIME_PREFIXES: tuple[str, ...] = ()

#: Storage directory — files are stored outside the static/ tree.
def _storage_dir() -> Path:
    """
    Returns the directory where uploaded files are stored.
    LNbits keeps user data under lnbits/data/; we follow the same pattern.
    The directory is created on first use.
    """
    from lnbits.settings import settings  # imported late to avoid circular import

    base = Path(settings.lnbits_data_folder) / "files4sats"
    base.mkdir(parents=True, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _safe_extension(filename: str) -> str:
    """Return the lowercased extension of *filename*, e.g. '.zip'."""
    return Path(filename).suffix.lower()


async def save_uploaded_file(upload: UploadFile) -> tuple[str, str, str, int, str]:
    """
    Persist *upload* to disk under a UUID-based name.

    Returns:
        (original_filename, storage_filename, mime_type, file_size_bytes, sha256_hex)

    Raises HTTPException on oversized or invalid uploads.
    Never trusts the client-supplied Content-Type for anything security-sensitive.
    """
    original_name = Path(upload.filename or "file").name  # strip any path component

    # Determine MIME from extension; fall back to octet-stream
    guessed_mime, _ = mimetypes.guess_type(original_name)
    mime_type = guessed_mime or "application/octet-stream"

    ext = _safe_extension(original_name)
    storage_name = f"{urlsafe_short_hash()}{ext}"
    dest_path = _storage_dir() / storage_name

    sha256 = hashlib.sha256()
    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KiB chunks — efficient for large files

    try:
        with dest_path.open("wb") as fh:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    fh.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        f"File exceeds the maximum allowed size of "
                        f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.",
                    )
                sha256.update(chunk)
                fh.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        logger.error(f"files4sats: error saving upload: {exc}")
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not save the uploaded file.")

    return original_name, storage_name, mime_type, total_bytes, sha256.hexdigest()


def delete_stored_file(storage_name: str) -> None:
    """Remove a stored file from disk.  Silently ignores missing files."""
    path = _storage_dir() / storage_name
    path.unlink(missing_ok=True)


def get_file_path(storage_name: str) -> Path:
    """Return the absolute path for a stored file, blocking path-traversal attempts."""
    storage = _storage_dir()
    target = (storage / storage_name).resolve()
    # Ensure the resolved path is still inside our storage directory
    if not str(target).startswith(str(storage.resolve())):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid file reference.")
    if not target.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "File not found.")
    return target


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------


async def verify_integrity(product_id: str, code: str) -> VerifyIntegrityResponse:
    """
    Compare the buyer-supplied *code* against the stored SHA-256.

    - Uses hmac.compare_digest for timing-safe comparison.
    - Never returns the expected hash in any form.
    - Creates a one-time integrity_token stored in a new Purchase row.
    """
    import hmac

    product = await get_product(product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")

    # Normalise: lowercase hex, strip whitespace
    submitted = code.strip().lower()

    # Timing-safe compare
    if not hmac.compare_digest(product.sha256_hash.lower(), submitted):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid integrity code.")

    # Issue a one-time token
    token = urlsafe_short_hash()
    purchase = Purchase(
        id=urlsafe_short_hash(),
        product_id=product_id,
        integrity_token=token,
        integrity_verified=True,
        paid=False,
    )
    await create_purchase(purchase)
    return VerifyIntegrityResponse(integrity_token=token)


# ---------------------------------------------------------------------------
# Invoice creation
# ---------------------------------------------------------------------------


async def create_purchase_invoice(
    product_id: str, integrity_token: str | None
) -> InvoiceResponse:
    """
    Create a Lightning invoice for *product_id*.

    If the product requires integrity verification, *integrity_token* must match
    a verified (but not yet paid) Purchase row.  This is validated server-side;
    the frontend cannot bypass it.
    """
    product = await get_product(product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")

    purchase: Purchase | None = None

    if product.require_integrity:
        if not integrity_token:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Integrity code required before creating an invoice.",
            )
        purchase = await get_purchase_by_integrity_token(integrity_token)
        if not purchase or not purchase.integrity_verified or purchase.product_id != product_id:
            raise HTTPException(
                HTTPStatus.FORBIDDEN,
                "Invalid or expired integrity token.",
            )
        if purchase.paid:
            raise HTTPException(HTTPStatus.CONFLICT, "This purchase has already been paid.")
        if purchase.payment_hash:
            # Token was already used to generate an invoice — return the same one
            return InvoiceResponse(
                purchase_id=purchase.id,
                payment_hash=purchase.payment_hash,
                payment_request=purchase.payment_request or "",
            )
    else:
        # No integrity gate — create a fresh purchase row
        purchase = Purchase(
            id=urlsafe_short_hash(),
            product_id=product_id,
            integrity_verified=False,
        )
        await create_purchase(purchase)

    # Create the LNbits invoice
    payment: Payment = await create_invoice(
        wallet_id=product.wallet_id,
        amount=product.price_sats,
        currency="sat",
        extra={"tag": "filesforsats", "purchase_id": purchase.id},
        memo=f"files4sats: {product.name} [{purchase.id[:8]}]",
    )

    purchase.payment_hash = payment.payment_hash
    purchase.payment_request = payment.bolt11
    await update_purchase(purchase)

    return InvoiceResponse(
        purchase_id=purchase.id,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
    )


# ---------------------------------------------------------------------------
# Payment webhook handler (called from tasks.py)
# ---------------------------------------------------------------------------


async def payment_received(payment: Payment) -> bool:
    """
    Called when a files4sats invoice is confirmed paid.
    Marks the Purchase as paid so the download endpoint can serve the file.
    """
    purchase_id = payment.extra.get("purchase_id")
    if not purchase_id:
        logger.warning("files4sats: payment has no purchase_id in extra.")
        return False

    purchase = await get_purchase_by_payment_hash(payment.payment_hash)
    if not purchase:
        logger.warning(f"files4sats: no purchase found for hash {payment.payment_hash}")
        return False

    purchase.paid = True
    await update_purchase(purchase)
    logger.info(f"files4sats: purchase {purchase.id} marked as paid.")
    return True
