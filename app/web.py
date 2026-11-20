from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from .config import PROJECT, ROOT, SAMPLES, TITLE
from .pipeline import preview

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "app" / "templates")


@router.get("/", include_in_schema=False)
def workbench(request: Request, sample: str = "dirty"):
    return templates.TemplateResponse(request=request, name="workbench.html", context={
        "title": TITLE, "project": PROJECT, "samples": SAMPLES, "sample": sample,
        "initial": preview(sample),
    })


@router.get("/api/previews/{sample}")
def preview_batch(sample: str):
    return preview(sample)
