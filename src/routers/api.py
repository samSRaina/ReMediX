from fastapi import APIRouter
import src.services.logic as func

router= APIRouter(prefix="/api")

@router.get("smile/{smile_id}")
def get_smile_api(smile_id: str):
    return func.get_smile(smile_id)