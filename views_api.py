"""
API views for the filesforsats extension.

Endpoint summary
----------------
Seller (authenticated):
  POST   /api/v1/products          — upload file + create product
  GET    /api/v1/products/paginated — list seller's products
  GET    /api/v1/products/{id}     — get single product (includes sha256_hash)
  DELETE /api/v1/products/{id}     — delete product + file on disk

Buyer (public):
  GET    /api/v1/products/{id}/public          — public product info (no hash)
  POST   /api/v1/products/{id}/verify          — integrity code check
  POST   /api/v1/products/{id}/invoice         — create LN invoice
  GET    /api/v1/purchases/{payment_hash}/status — poll payment status

Download (public but guarded by paid state):
  GET    /api/v1/download/{payment_hash}       — stream file after payment
"""

from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse
from lnbits.core.models import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.db import Filters, Page
from lnbits.decorators import check_account_id_exists, check_admin, parse_filters
from lnbits.helpers import generate_filter_params_openapi, urlsafe_short_hash

from .crud import (
    create_product,
    delete_product,
    get_admin_settings,
    get_product,
    get_product_owned,
    get_products_paginated,
    get_purchase_by_payment_hash,
    get_user_storage_usage,
    upsert_admin_settings,
    upsert_unlock_record,
)
from .models import (
    AdminSettings,
    CreateInvoiceRequest,
    InvoiceResponse,
    PaymentStatusResponse,
    Product,
    ProductFilters,
    PublicProduct,
    UpdateAdminSettings,
    VerifyIntegrityRequest,
    VerifyIntegrityResponse,
)
from .services import (
    create_purchase_invoice,
    delete_stored_file,
    get_file_path,
    save_uploaded_file,
    verify_integrity,
)

product_filters = parse_filters(ProductFilters)

filesforsats_api_router = APIRouter()


# ===========================================================================
# Admin-only endpoints
# ===========================================================================


@filesforsats_api_router.get(
    "/api/v1/admin/settings",
    summary="Get admin settings (commission & unlock mode)",
    response_model=AdminSettings,
    dependencies=[Depends(check_admin)],
)
async def api_get_admin_settings() -> AdminSettings:
    return await get_admin_settings()


@filesforsats_api_router.put(
    "/api/v1/admin/settings",
    summary="Update admin settings (commission & unlock mode)",
    response_model=AdminSettings,
    dependencies=[Depends(check_admin)],
)
async def api_update_admin_settings(body: UpdateAdminSettings) -> AdminSettings:
    current = await get_admin_settings()
    updated = AdminSettings(
        id=current.id,
        commission_percent=body.commission_percent,
        commission_wallet_id=body.commission_wallet_id,
        unlock_monthly=body.unlock_monthly,
        storage_quota_mb=body.storage_quota_mb,
    )
    return await upsert_admin_settings(updated)


@filesforsats_api_router.post(
    "/api/v1/unlock/confirm",
    summary="Record a successful extension unlock payment for a user",
    response_model=SimpleStatus,
    dependencies=[Depends(check_account_id_exists)],
)
async def api_confirm_unlock(
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    """
    Called by the frontend immediately after the user's pay-to-enable invoice
    is confirmed paid.  Stamps the current UTC time in unlock_records so
    the monthly-expiry background task knows when the 30-day window began.
    """
    await upsert_unlock_record(account_id.id)
    return SimpleStatus(success=True, message="Unlock timestamp recorded.")


@filesforsats_api_router.post(
    "/api/v1/products",
    status_code=HTTPStatus.CREATED,
    summary="Upload a file and create a product",
    response_model=Product,
)
async def api_create_product(
    name: str = Form(...),
    description: str = Form(""),
    price_sats: int = Form(...),
    wallet_id: str = Form(...),
    require_integrity: bool = Form(True),
    file: UploadFile = File(...),
    account_id: AccountId = Depends(check_account_id_exists),
) -> Product:
    """
    Multipart upload endpoint.
    The server computes the SHA-256 hash of the uploaded file.
    The hash is stored in the DB and returned to the seller so they can share
    it privately with the buyer.  It is never exposed on any public endpoint.
    """
    if not file.filename:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "No file provided.")

    admin_cfg = await get_admin_settings()
    max_quota_bytes = admin_cfg.storage_quota_mb * 1024 * 1024
    used_bytes = await get_user_storage_usage(account_id.id)
    remaining_bytes = max(0, max_quota_bytes - used_bytes)

    if remaining_bytes <= 0:
        raise HTTPException(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Storage quota exceeded. Please delete some files to free up space."
        )

    # 2. Process and save the uploaded file, enforcing the remaining quota
    original_name, storage_name, mime_type, file_size, sha256_hash = await save_uploaded_file(
        file, max_allowed_bytes=remaining_bytes
    )

    product = Product(
        id=urlsafe_short_hash(),
        user_id=account_id.id,
        wallet_id=wallet_id,
        name=name,
        description=description,
        price_sats=price_sats,
        file_name=original_name,
        storage_name=storage_name,
        mime_type=mime_type,
        file_size=file_size,
        sha256_hash=sha256_hash,
        require_integrity=require_integrity,
    )
    return await create_product(product)


@filesforsats_api_router.get(
    "/api/v1/storage/usage",
    summary="Get user's total storage usage",
    dependencies=[Depends(check_account_id_exists)],
)
async def api_get_storage_usage(
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    admin_cfg = await get_admin_settings()
    used_bytes = await get_user_storage_usage(account_id.id)
    limit_bytes = admin_cfg.storage_quota_mb * 1024 * 1024

    return {
        "used_bytes": used_bytes,
        "limit_bytes": limit_bytes,
    }


@filesforsats_api_router.get(
    "/api/v1/products/paginated",
    summary="List seller's products (paginated)",
    openapi_extra=generate_filter_params_openapi(ProductFilters),
    response_model=Page[Product],
)
async def api_get_products_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    filters: Filters = Depends(product_filters),
) -> Page[Product]:
    return await get_products_paginated(user_id=account_id.id, filters=filters)


@filesforsats_api_router.get(
    "/api/v1/products/{product_id}",
    summary="Get a product (seller view — includes sha256_hash)",
    response_model=Product,
)
async def api_get_product(
    product_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Product:
    product = await get_product_owned(account_id.id, product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")
    return product


@filesforsats_api_router.delete(
    "/api/v1/products/{product_id}",
    summary="Delete a product and its stored file",
    response_model=SimpleStatus,
)
async def api_delete_product(
    product_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    product = await get_product_owned(account_id.id, product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")

    # Remove file from disk before removing DB row
    delete_stored_file(product.storage_name)
    await delete_product(account_id.id, product_id)
    return SimpleStatus(success=True, message="Product deleted.")


# ===========================================================================
# Public / buyer endpoints (no authentication required)
# ===========================================================================


@filesforsats_api_router.get(
    "/api/v1/products/{product_id}/public",
    summary="Get public product info (no hash, safe for buyers)",
    response_model=PublicProduct,
)
async def api_get_public_product(product_id: str) -> PublicProduct:
    product = await get_product(product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")
    admin_cfg = await get_admin_settings()
    # PublicProduct deliberately omits sha256_hash.
    # commission_percent is exposed so a seller-side banner can display the rate.
    return PublicProduct(
        id=product.id,
        name=product.name,
        description=product.description,
        price_sats=product.price_sats,
        require_integrity=product.require_integrity,
        file_name=product.file_name,
        file_size=product.file_size,
        mime_type=product.mime_type,
        commission_percent=admin_cfg.commission_percent,
    )


@filesforsats_api_router.post(
    "/api/v1/products/{product_id}/verify",
    summary="Submit integrity code — returns opaque token on success",
    response_model=VerifyIntegrityResponse,
)
async def api_verify_integrity(
    product_id: str,
    body: VerifyIntegrityRequest,
) -> VerifyIntegrityResponse:
    """
    The buyer submits the SHA-256 hex hash they received from the seller.
    The backend compares it server-side.  The response never includes the
    expected hash — only an opaque token proving the check passed.
    """
    return await verify_integrity(product_id, body.code)


@filesforsats_api_router.post(
    "/api/v1/products/{product_id}/invoice",
    summary="Create a Lightning invoice for a product purchase",
    response_model=InvoiceResponse,
    status_code=HTTPStatus.CREATED,
)
async def api_create_invoice(
    product_id: str,
    body: CreateInvoiceRequest,
) -> InvoiceResponse:
    """
    If the product requires integrity verification, the buyer must supply the
    integrity_token obtained from /verify.  The server validates this token
    before creating any invoice.
    """
    return await create_purchase_invoice(product_id, body.integrity_token)


@filesforsats_api_router.get(
    "/api/v1/purchases/{payment_hash}/status",
    summary="Poll payment status for a purchase",
    response_model=PaymentStatusResponse,
)
async def api_get_payment_status(payment_hash: str) -> PaymentStatusResponse:
    """
    Public polling endpoint — returns only {paid: bool}.
    The frontend should prefer the WebSocket at /api/v1/ws/{payment_hash}
    and fall back to polling this endpoint.
    """
    purchase = await get_purchase_by_payment_hash(payment_hash)
    if not purchase:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Purchase not found.")
    return PaymentStatusResponse(paid=purchase.paid)


# ===========================================================================
# Protected download endpoint
# ===========================================================================


@filesforsats_api_router.get(
    "/api/v1/download/{payment_hash}",
    summary="Download file — only available after confirmed payment",
)
async def api_download_file(payment_hash: str) -> FileResponse:
    """
    Server-side payment check before any file is served.
    Files live outside the static/ directory and are never accessible via
    direct URL — this is the only way to get them.
    """
    purchase = await get_purchase_by_payment_hash(payment_hash)
    if not purchase:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Purchase not found.")
    if not purchase.paid:
        raise HTTPException(
            HTTPStatus.PAYMENT_REQUIRED,
            "Payment has not been confirmed yet.",
        )

    product = await get_product(purchase.product_id)
    if not product:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Product not found.")

    file_path: Path = get_file_path(product.storage_name)

    return FileResponse(
        path=str(file_path),
        media_type=product.mime_type,
        filename=product.file_name,
    )


@filesforsats_api_router.get(
    "/api/v1/about",
    summary="Get extension configuration information (config.json)",
)
async def api_get_about():
    """Reads and serves the config.json for the frontend About dialog."""
    import json
    from pathlib import Path

    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
