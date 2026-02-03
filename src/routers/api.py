
from fastapi import APIRouter
import src.services.logic as func

router= APIRouter(prefix="/api")

@router.get("/smile/{smile_id}")
async def get_smile_api(smile_id: str):
    return func.get_smile(smile_id)

@router.get("/properties/{compound}")
async def get_compound_properties_api(compound: str):
    return func.get_properties(compound)
