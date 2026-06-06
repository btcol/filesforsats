import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import filesforsats_generic_router
from .views_api import filesforsats_api_router

filesforsats_ext: APIRouter = APIRouter(
    prefix="/filesforsats", tags=["filesforsats"]
)
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
    task = create_permanent_unique_task("ext_filesforsats", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "db",
    "filesforsats_ext",
    "filesforsats_start",
    "filesforsats_static_files",
    "filesforsats_stop",
]