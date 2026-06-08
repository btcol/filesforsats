import pytest

from filesforsats.crud import get_admin_settings  # type: ignore[import]
from filesforsats.models import AdminSettings  # type: ignore[import]


@pytest.mark.asyncio
async def test_get_admin_settings():
    settings = await get_admin_settings()
    assert isinstance(settings, AdminSettings)
