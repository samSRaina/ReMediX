
from fastapi import APIRouter, HTTPException
from typing import Optional
from ..clients import pubchem_client, drugbank_client, chembl_client, creeds_client, geneCards_client
router= APIRouter(prefix="/api")

#@router.get("/smile/{smile_id}")
#async def get_smile_api(smile_id: str):
#    return func.get_smile(smile_id)

# PubChem database endpoints
@router.get("/compound/name/{name}/properties")
async def get_properties_by_name_api(name: str):
    return pubchem_client.PubChemClient().search_by_name(name)


@router.get("/compound/smile/{smile}/properties")
async def get_properties_by_smile_api(smile: str):
    return pubchem_client.PubChemClient().search_by_smile(smile)


# DrugBank database endpoints
@router.get("/drugbank/inchikey/{inchikey}/properties")
async def get_properties_by_inchikey(inchikey: str):
    result = drugbank_client.DrugBankClient()
    if result is None:
        raise HTTPException(status_code=404, detail=f"Drug '{inchikey}' not found in DrugBank database")
    return result.search_drug_by_inchikey(inchikey)


# ChEMBL database endpoints
@router.get("/chembl/inchikey/{inchikey}/bioactivity")
async def get_bioactivity_by_inchikey(inchikey: str, standard_type: Optional[str] = None):
    result = chembl_client.ChEMBLClient().get_by_inchikey(inchikey, standard_type)
    if not result:
        raise HTTPException(status_code=404, detail=f"No bioactivity data found for '{inchikey}'")
    return result

@router.get("/chembl/inchikey/{inchkey}/bioactivity/{target_chembl_id}/target")
async def get_target_data(target_chembl_id: str):
    result = chembl_client.ChEMBLClient().get_target_data(target_chembl_id)
    if not result:
        raise HTTPException(status_code =404, detail=f"No target data found for {target_chembl_id}")
    return result

@router.get("/geneAnalysis/accession/{accession_id}")
async def get_gene_analysis(accession_id: str, disease: str):
    disease_signatures = creeds_client.get_disease_signatures(disease)
    accession_object = creeds_client.CreedsClient(accession_id)
    single_gene_perturbations = accession_object.get_single_gene_perturbations()
    return accession_object.match_genes(disease_signatures, single_gene_perturbations )

@router.get("/geneExpressions")
async def get_gene_expressions(page: int = 1, page_size: int = 50, search: Optional[str] = None):
    all_data = geneCards_client.get_geo_data()

    # Filter by search term (searches Gene.symbol column)
    if search:
        search_lower = search.lower()
        all_data = [
            row for row in all_data
            if row.get("Gene.symbol") and search_lower in str(row["Gene.symbol"]).lower()
        ]

    total = len(all_data)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "data": all_data[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
