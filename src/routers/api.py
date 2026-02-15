
from fastapi import APIRouter, HTTPException
from ..clients import pubchem_client, drugbank_client
router= APIRouter(prefix="/api")

#@router.get("/smile/{smile_id}")
#async def get_smile_api(smile_id: str):
#    return func.get_smile(smile_id)

@router.get("/compound/name/{name}/properties")
async def get_properties_by_name_api(name : str):
    return pubchem_client.PubChemClient().search_by_name(name)


@router.get("/compound/smile/{smile}/properties")
async def get_properties_by_smile_api(smile: str):
    return pubchem_client.PubChemClient().search_by_smile(smile)


# DrugBank database endpoints
@router.get("/drugbank/inchikey/{inchikey}")
async def get_properties_by_inchikey(inchikey: str):
    result = drugbank_client.DrugBankClient()
    if result is None:
        raise HTTPException(status_code=404, detail=f"Drug '{inchikey}' not found in DrugBank database")
    return result.search_drug_by_inchikey(inchikey)
