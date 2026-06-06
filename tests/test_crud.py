from uuid import uuid4

import pytest

from filesforsats.crud import (  # type: ignore[import]
    create_merchants,
    delete_merchants,
    get_merchants,
    get_merchants_by_id,
    get_merchants_ids_by_user,
    get_merchants_paginated,
    update_merchants,
)
from filesforsats.models import (  # type: ignore[import]
    CreateMerchants,
    Merchants,
)


@pytest.mark.asyncio
async def test_create_and_get_merchants():
    user_id = uuid4().hex

    data = CreateMerchants(
        name = "name_WDQHukVZojtiHZ2nUcJEvk",
        mail = "mail_LYEMgLvR6MoCJxN3gHPd5p",
        currency = "sat",
        amount = 16,
        paiddown = False,
        wallet = "7d630406-50b0-49f6-ab3f-634d3f426c16",
    )
    merchants_one = await create_merchants(user_id, data)
    assert merchants_one.id is not None
    assert merchants_one.user_id == user_id

    merchants_one = await get_merchants(user_id, merchants_one.id)
    assert merchants_one.id is not None
    assert merchants_one.user_id == user_id
    assert merchants_one.name == data.name
    assert merchants_one.mail == data.mail
    assert merchants_one.currency == data.currency
    assert merchants_one.amount == data.amount
    assert merchants_one.paiddown == data.paiddown
    assert merchants_one.wallet == data.wallet

    data = CreateMerchants(
        name = "name_WDQHukVZojtiHZ2nUcJEvk",
        mail = "mail_LYEMgLvR6MoCJxN3gHPd5p",
        currency = "sat",
        amount = 16,
        paiddown = False,
        wallet = "7d630406-50b0-49f6-ab3f-634d3f426c16",
    )
    merchants_two = await create_merchants(user_id, data)
    assert merchants_two.id is not None
    assert merchants_two.user_id == user_id

    merchants_list = await get_merchants_ids_by_user(user_id=user_id)
    assert len(merchants_list) == 2

    merchants_page = await get_merchants_paginated(user_id=user_id)
    assert merchants_page.total == 2
    assert len(merchants_page.data) == 2

    await delete_merchants(user_id, merchants_one.id)
    merchants_list = await get_merchants_ids_by_user(user_id=user_id)
    assert len(merchants_list) == 1

    merchants_page = await get_merchants_paginated(user_id=user_id)
    assert merchants_page.total == 1
    assert len(merchants_page.data) == 1


@pytest.mark.asyncio
async def test_update_merchants():
    user_id = uuid4().hex

    data = CreateMerchants(
        name = "name_WDQHukVZojtiHZ2nUcJEvk",
        mail = "mail_LYEMgLvR6MoCJxN3gHPd5p",
        currency = "sat",
        amount = 16,
        paiddown = False,
        wallet = "7d630406-50b0-49f6-ab3f-634d3f426c16",
    )
    merchants_one = await create_merchants(user_id, data)
    assert merchants_one.id is not None
    assert merchants_one.user_id == user_id

    merchants_one = await get_merchants(user_id, merchants_one.id)
    assert merchants_one.id is not None
    assert merchants_one.user_id == user_id
    assert merchants_one.name == data.name
    assert merchants_one.mail == data.mail
    assert merchants_one.currency == data.currency
    assert merchants_one.amount == data.amount
    assert merchants_one.paiddown == data.paiddown
    assert merchants_one.wallet == data.wallet

    data_updated = CreateMerchants(
        name = "name_WDQHukVZojtiHZ2nUcJEvk",
        mail = "mail_LYEMgLvR6MoCJxN3gHPd5p",
        currency = "sat",
        amount = 16,
        paiddown = False,
        wallet = "7d630406-50b0-49f6-ab3f-634d3f426c16",
    )
    merchants_updated = Merchants(**{**merchants_one.dict(), **data_updated.dict()})

    await update_merchants(merchants_updated)
    merchants_one = await get_merchants_by_id(merchants_one.id)
    assert merchants_one.name == merchants_updated.name
    assert merchants_one.mail == merchants_updated.mail
    assert merchants_one.currency == merchants_updated.currency
    assert merchants_one.amount == merchants_updated.amount
    assert merchants_one.paiddown == merchants_updated.paiddown
    assert merchants_one.wallet == merchants_updated.wallet
