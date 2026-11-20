from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import PROJECT, ROOT, RULESET, TITLE, database_path
from .errors import DomainError, respond
from .modules.m1_orders import handler as orders
from .modules.m2_substitutions import handler as substitutions
from .modules.m3_windows import handler as windows
from .modules.m4_capacity import handler as capacity
from .modules.m5_allocation import handler as allocation
from .modules.m6_reconcile import handler as reconcile
from .modules.m7_archive import handler as archive
from .modules.m8_rescue import handler as rescue
from .store import Ledger
from .web import router as web


def create_app(path=None):
    @asynccontextmanager
    async def lifespan(application):
        application.state.ledger = Ledger(path or database_path())
        yield

    application = FastAPI(title=TITLE, lifespan=lifespan)
    application.add_exception_handler(DomainError, respond)
    application.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    for module in (orders, substitutions, windows, capacity, allocation, reconcile, archive, rescue):
        application.include_router(module.router)
    application.include_router(web)

    @application.get("/api/health")
    def health():
        return {"status": "ok", "project": PROJECT, "ruleset": RULESET}

    return application


app = create_app()
