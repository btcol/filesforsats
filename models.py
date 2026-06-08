from datetime import datetime, timezone

from lnbits.db import FilterModel
from pydantic import BaseModel, Field, validator

# ---------------------------------------------------------------------------
# Admin Settings — single-row configuration owned by the extension admin
# ---------------------------------------------------------------------------


class AdminSettings(BaseModel):
    """The extension-level admin configuration (stored as a single DB row)."""

    id: int = 1
    commission_percent: float = Field(0.0, ge=0, le=100)
    commission_wallet_id: str = ""
    unlock_monthly: bool = False
    storage_quota_mb: int = Field(1024, ge=1)
    default_currency: str = "sat"


class UpdateAdminSettings(BaseModel):
    """Payload for PUT /api/v1/admin/settings."""

    commission_percent: float = Field(0.0, ge=0, le=100)
    commission_wallet_id: str = ""
    unlock_monthly: bool = False
    storage_quota_mb: int = Field(1024, ge=1)
    default_currency: str = "sat"

    @validator("commission_percent")
    def _round_percent(cls, v):
        return round(v, 4)


# ---------------------------------------------------------------------------
# Product — what the seller creates
# ---------------------------------------------------------------------------


class CreateProduct(BaseModel):
    """Payload for POST /api/v1/products (multipart, handled in views_api)."""

    name: str
    description: str = ""
    price_sats: int
    price: float
    currency: str = "sat"
    wallet_id: str
    require_integrity: bool = True


class Product(BaseModel):
    id: str
    user_id: str
    wallet_id: str
    name: str
    description: str
    price_sats: int
    price: float
    currency: str = "sat"
    file_name: str  # Original user-provided name (for Content-Disposition)
    storage_name: str  # UUID-based name on disk (never exposed)
    mime_type: str
    file_size: int
    sha256_hash: str  # Server-computed SHA-256 hex digest (seller-only)
    require_integrity: bool

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicProduct(BaseModel):
    """Safe projection for the buyer's public page — never includes sha256_hash."""

    id: str
    name: str
    description: str
    price_sats: int
    price: float
    currency: str = "sat"
    require_integrity: bool
    file_name: str
    file_size: int
    mime_type: str
    commission_percent: float = 0.0  # Informational: shown to seller, never used for payment calc on client


class ProductFilters(FilterModel):
    __search_fields__ = ["name", "description"]
    __sort_fields__ = ["name", "price_sats", "price", "created_at", "updated_at"]

    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Purchase — one buyer transaction
# ---------------------------------------------------------------------------


class Purchase(BaseModel):
    id: str
    product_id: str
    payment_hash: str | None = None
    payment_request: str | None = None
    integrity_token: str | None = None
    integrity_verified: bool = False
    paid: bool = False

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Request / Response helpers
# ---------------------------------------------------------------------------


class VerifyIntegrityRequest(BaseModel):
    """Buyer submits the SHA-256 hash they received from the seller."""

    code: str


class VerifyIntegrityResponse(BaseModel):
    """Opaque token to prove the buyer passed verification."""

    integrity_token: str


class CreateInvoiceRequest(BaseModel):
    """Buyer exchanges integrity_token for a Lightning invoice."""

    integrity_token: str


class InvoiceResponse(BaseModel):
    purchase_id: str
    payment_hash: str
    payment_request: str


class PaymentStatusResponse(BaseModel):
    paid: bool
