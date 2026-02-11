
from fastapi import APIRouter, HTTPException
import src.services.logic as func
import src.services.drugbank_parser as drugbank

router= APIRouter(prefix="/api")

#@router.get("/smile/{smile_id}")
#async def get_smile_api(smile_id: str):
#    return func.get_smile(smile_id)

@router.get("/compound/name/{name}/properties")
async def get_properties_api(name : str):
    return func.get_pubchem_properties(name)


@router.get("/compound/smile/{smile}/properties")
async def get_properties_via_smile_api(smile: str):
    return func.get_pubchem_properties_via_smile(smile)


# DrugBank database endpoints
@router.get("/drugbank/inchikey/{inchikey}")
async def get_drug_by_inchikey_api(inchikey: str):
    result = drugbank.get_drug_by_inchikey(inchikey)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Drug '{inchikey}' not found in DrugBank database")
    return result
