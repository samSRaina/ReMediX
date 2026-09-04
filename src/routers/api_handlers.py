from pathlib import Path
import re
from typing import Optional

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from ..clients import chembl_client, creeds_client, drugbank_client, geneCards_client, pubchem_client
from ..data_availability import require_dataset
from ..utils import final_gene_score, remedix_scoring

_drugbank_client = drugbank_client.DrugBankClient()
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _format_image_label(filename: str) -> str:
    stem = Path(filename).stem
    label = re.sub(r"[_-]+", " ", stem)
    label = re.sub(r"\s+", " ", label).strip()
    return label or stem


# PubChem database endpoints
async def get_properties_by_name_api(name: str):
    result = await run_in_threadpool(pubchem_client.PubChemClient().search_by_name, name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Compound '{name}' not found in PubChem")
    return result


async def get_properties_by_smile_api(smile: str):
    result = await run_in_threadpool(pubchem_client.PubChemClient().search_by_smile, smile)
    if not result:
        raise HTTPException(status_code=404, detail="Compound not found in PubChem for the provided SMILES")
    return result


# DrugBank database endpoints
async def get_properties_by_inchikey(inchikey: str):
    require_dataset("drugbank")
    try:
        result = await run_in_threadpool(_drugbank_client.search_drug_by_inchikey, inchikey)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Drug '{inchikey}' not found in DrugBank database")
    return result


# ChEMBL database endpoints
async def get_bioactivity_by_inchikey(inchikey: str, standard_type: Optional[str] = None):
    chembl = chembl_client.ChEMBLClient()
    try:
        result = await run_in_threadpool(chembl.get_by_inchikey, inchikey, standard_type)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Distinguish "compound has no activity data at all" from "filter has no
    # matches". Uses a 1-row existence probe — never a full unfiltered fetch.
    if not result and not await run_in_threadpool(chembl.has_bioactivity_data, inchikey):
        raise HTTPException(status_code=404, detail=f"No bioactivity data found for '{inchikey}'")
    gene_set = await run_in_threadpool(chembl.get_gene_set, inchikey)
    aggregated_targets = await run_in_threadpool(chembl.get_aggregated_targets_by_inchikey, inchikey)
    return {"activities": result, "gene_set": sorted(gene_set), "aggregated_targets": aggregated_targets}


# CREEDS match endpoint - matches each gene against disease signatures
async def get_gene_match(genes: str, disease: str):
    """genes = comma-separated gene symbols, disease = target disease name (required)"""
    gene_list = [g.strip() for g in genes.split(",") if g.strip()]
    if not gene_list:
        raise HTTPException(status_code=400, detail="No genes provided")
    if not disease or not disease.strip():
        raise HTTPException(status_code=400, detail="Disease parameter is required")
    require_dataset("creeds_signatures", "creeds_perturbations")
    return await run_in_threadpool(creeds_client.match_gene_set, gene_list, disease)


async def get_final_gene_score(genes: str, disease: str):
    """
    Calculate final score based on non-ambiguous directional matches.
    Sum 'Final Score' from 'Final Gene Score' sheet for classified genes,
    then divide by predefined DIVISOR.
    """
    require_dataset("creeds_signatures", "creeds_perturbations")
    try:
        return await run_in_threadpool(final_gene_score.calculate_final_score, genes, disease)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_remedix_score(inchikey: str, disease: str):
    if not inchikey or not inchikey.strip():
        raise HTTPException(status_code=400, detail="InChIKey parameter is required")
    if not disease or not disease.strip():
        raise HTTPException(status_code=400, detail="Disease parameter is required")

    require_dataset("creeds_signatures")

    chembl = chembl_client.ChEMBLClient()
    aggregated_targets = await run_in_threadpool(chembl.get_aggregated_targets_by_inchikey, inchikey)
    raw_activities = await run_in_threadpool(chembl.get_by_inchikey, inchikey)

    try:
        scoring = await run_in_threadpool(remedix_scoring.calculate_remedix_score, aggregated_targets, disease)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "inchikey": inchikey,
        "disease": disease,
        "aggregated_targets": aggregated_targets,
        "raw_activities": raw_activities,
        "scoring": scoring,
    }


async def get_target_data(inchikey: str, target_chembl_id: str):
    # inchikey is part of route contract but target lookup only needs target_chembl_id.
    _ = inchikey
    result = await run_in_threadpool(chembl_client.ChEMBLClient().get_target_data, target_chembl_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No target data found for {target_chembl_id}")
    return result


async def get_gene_analysis(accession_id: str, disease: str):
    require_dataset("creeds_signatures", "creeds_perturbations")
    disease_signatures = creeds_client.get_disease_signatures(disease)
    accession_object = creeds_client.CreedsClient(accession_id)
    single_gene_perturbations = await run_in_threadpool(accession_object.get_single_drug_perturbations)
    return accession_object.match_genes(disease_signatures, single_gene_perturbations)


async def get_gene_expressions(page: int = 1, page_size: int = 50, search: Optional[str] = None):
    require_dataset("geo")
    return await run_in_threadpool(geneCards_client.get_geo_data, page, page_size, search)


async def get_gene_expression_images():
    require_dataset("ppi_images", refresh=True)
    data_dir = Path(__file__).resolve().parent.parent / "data" / "PPInteraction"
    if not data_dir.exists():
        return {"images": []}

    images = []
    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        images.append(
            {
                "label": _format_image_label(path.name),
                "url": f"/data/PPInteraction/{path.name}",
                "filename": path.name,
            }
        )
    return {"images": images}


async def get_excel_meta():
    """Return sheet names, column headers and row counts (lightweight)."""
    require_dataset("ppi_xlsx")
    sheets = await run_in_threadpool(final_gene_score.load_excel_sheets)
    meta = {}
    for name, rows in sheets.items():
        headers = rows[0] if rows else []
        meta[name] = {
            "headers": headers,
            "totalRows": max(0, len(rows) - 1),  # exclude header
        }
    return {"sheetNames": list(sheets.keys()), "meta": meta}


async def get_excel_sheet(name: str, page: int = 1, page_size: int = 100):
    """Return a paginated slice of one sheet's data rows."""
    require_dataset("ppi_xlsx")
    sheets = await run_in_threadpool(final_gene_score.load_excel_sheets)
    if name not in sheets:
        raise HTTPException(status_code=404, detail=f"Sheet '{name}' not found")

    all_rows = sheets[name]
    headers = all_rows[0] if all_rows else []
    data_rows = all_rows[1:]  # everything after header

    total = len(data_rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "headers": headers,
        "data": data_rows[start:end],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
    }


async def get_disease_signature_table(disease: str, page: int = 1, page_size: int = 100):
    """Return a paginated disease signature table. Disease parameter is required."""
    if not disease or not disease.strip():
        raise HTTPException(status_code=400, detail="Disease parameter is required")
    require_dataset("creeds_signatures")
    try:
        payload = await run_in_threadpool(creeds_client.build_disease_signature_table, disease)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rows = payload.get("rows", [])
    headers = payload.get("headers", [])
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "disease": payload.get("disease", disease),
        "headers": headers,
        "data": rows[start:end],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
    }


async def get_available_diseases():
    """Return list of available diseases in CREEDS dataset."""
    require_dataset("creeds_signatures")
    dataset = await run_in_threadpool(creeds_client._load_disease_signature_dataset)
    diseases = sorted(
        set(str(entry.get("disease_name", "")).strip() for entry in dataset if entry.get("disease_name"))
    )
    return {"diseases": diseases}
