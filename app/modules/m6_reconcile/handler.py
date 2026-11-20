from fastapi import APIRouter

from app.pipeline import preview

router = APIRouter(prefix="/api/reconcile")


@router.get("/{sample}")
def inspect(sample: str):
    return preview(sample, "reconcile")
