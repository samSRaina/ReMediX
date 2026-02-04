
from fastapi import APIRouter
import src.services.logic as func

router= APIRouter(prefix="/api")

#@router.get("/smile/{smile_id}")
#async def get_smile_api(smile_id: str):
#    return func.get_smile(smile_id)

@router.get("/compound/name/{name}/properties")
async def get_properties_api(name : str):
    return func.get_properties(name)


@router.get("/compound/smile/{smile}/properties")
async def get_properties_via_smile_api(smile: str):
    return func.get_properties_via_smile(smile)