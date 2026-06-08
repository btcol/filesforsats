import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import check_monthly_unlocks, wait_for_paid_invoices
from .views import filesforsats_generic_router
from .views_api import filesforsats_api_router

filesforsats_ext: APIRouter = APIRouter(prefix="/filesforsats", tags=["filesforsats"])
filesforsats_ext.include_router(filesforsats_generic_router)
filesforsats_ext.include_router(filesforsats_api_router)


filesforsats_static_files = [
    {
        "path": "/filesforsats/static",
        "name": "filesforsats_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def filesforsats_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def filesforsats_start():
    task1 = create_permanent_unique_task("ext_filesforsats", wait_for_paid_invoices)
    task2 = create_permanent_unique_task("ext_filesforsats_monthly_unlock", check_monthly_unlocks)
    scheduled_tasks.extend([task1, task2])


__all__ = [
    "db",
    "filesforsats_ext",
    "filesforsats_start",
    "filesforsats_static_files",
    "filesforsats_stop",
]
