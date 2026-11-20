from fastapi import APIRouter, Request

from app.source import choose
from . import service
from .export import evidence

router = APIRouter(prefix="/api/runs")


@router.get("")
def history(request: Request):
    return {"runs": request.app.state.ledger.recent()}


@router.post("")
def run(body: dict, request: Request):
    return service.execute(request.app.state.ledger, choose(body))


@router.get("/{ident}")
def read(ident: str, request: Request):
    return request.app.state.ledger.read(ident)[1]


@router.post("/{ident}/rerun")
def rerun(ident: str, request: Request):
    return service.rerun(request.app.state.ledger, ident)


@router.post("/{ident}/sign")
def sign(ident: str, body: dict, request: Request):
    return service.sign(request.app.state.ledger, ident, body)


@router.get("/{ident}/export")
def export(ident: str, request: Request):
    return evidence(request.app.state.ledger, ident)
