from fastapi import APIRouter, Request

from app.errors import DomainError
from app.records import token
from . import service

router = APIRouter(prefix="/api/runs/{run_id}/rescues")


def _payload(body):
    if not isinstance(body, dict):
        raise DomainError("RESCUE_BAD_BODY", "救援请求须为 JSON 对象")
    failed_truck = body.get("failed_truck")
    if not token(failed_truck):
        raise DomainError("RESCUE_TRUCK_REQUIRED", "请指定故障车辆")
    backup = body.get("backup")
    if backup is not None and not isinstance(backup, dict):
        raise DomainError("BACKUP_SCHEMA", "备用车须为车次记录对象")
    return failed_truck.strip(), backup


@router.get("")
def history(run_id: str, request: Request):
    return service.history(request.app.state.ledger, run_id)


@router.post("/preview")
def preview(run_id: str, body: dict, request: Request):
    failed_truck, backup = _payload(body)
    return service.preview(request.app.state.ledger, run_id, failed_truck, backup)


@router.post("")
def publish(run_id: str, body: dict, request: Request):
    failed_truck, backup = _payload(body)
    return service.publish(request.app.state.ledger, run_id, failed_truck, backup)


@router.get("/{failed_truck}")
def read(run_id: str, failed_truck: str, request: Request):
    return service.read(request.app.state.ledger, run_id, failed_truck)
