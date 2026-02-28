from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = (Jinja2Templates(directory=Path(__file__).resolve().parent.parent/"static"/"templates"))

@router.get("/",include_in_schema=False, name="home")
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")

@router.get("/geneExpressions", include_in_schema=False, name="gene_expressions")
async def gene_expressions(request: Request):
    return templates.TemplateResponse(request, "gene_expressions.html")

