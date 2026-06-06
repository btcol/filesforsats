# Page routes for the files4sats extension.

from fastapi import APIRouter, Depends
from lnbits.core.views.generic import index, index_public
from lnbits.decorators import check_account_exists
from lnbits.helpers import template_renderer

filesforsats_generic_router = APIRouter()


def filesforsats_renderer():
    return template_renderer(["filesforsats/templates"])


# Seller dashboard (requires LNbits login)
filesforsats_generic_router.add_api_route(
    "/",
    methods=["GET"],
    endpoint=index,
    dependencies=[Depends(check_account_exists)],
)

# Public product page (no login required)
filesforsats_generic_router.add_api_route(
    "/{product_id}",
    methods=["GET"],
    endpoint=index_public,
)
