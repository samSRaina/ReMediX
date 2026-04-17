from functools import lru_cache
import math
import openpyxl
from pathlib import Path
from ..clients import creeds_client

DIVISOR = 283.4119365

_EXCLUDED_SHEETS = ["Reactome"]

@lru_cache(maxsize=1)
def load_excel_sheets() -> dict[str, list[list]]:
    """Read all non-excluded sheets once and cache them."""
    from datetime import datetime, date

    def _serialise(v):
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        if isinstance(v, (datetime, date)):
            return str(v)
        return v

    excel_path = Path(__file__).resolve().parent.parent / "data" / "data_set.xlsx"
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    result: dict[str, list[list]] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name in _EXCLUDED_SHEETS:
            continue
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cleaned = [_serialise(c) for c in row]
            # trim trailing None cells (Top Reactome has 453 cols, mostly empty)
            while cleaned and cleaned[-1] is None:
                cleaned.pop()
            rows.append(cleaned)
        result[sheet_name] = rows

    return result


def calculate_final_score(genes: str, disease: str) -> dict:
    """
    Calculate final score based on non-ambiguous directional matches.
    Sum 'Final Score' from 'Final Gene Score' sheet for classified genes,
    then divide by predefined DIVISOR.
    """
    if not genes:
        return {"score": 0.0}
    if not disease or not disease.strip():
        raise ValueError("Disease parameter is required for final score calculation")

    gene_list = [g.strip() for g in genes.split(",") if g.strip()]
    
    # 1. Get match results to find non-ambiguous directional genes
    match_data = creeds_client.match_gene_set(gene_list, disease)
    results = match_data.get("results", [])

    scored_genes = set()
    for r in results:
        if r.get("direction") in {"up", "down"}:
            scored_genes.add(r["gene"].strip().upper())

    if not scored_genes:
        return {"score": 0.0, "genes_counted": []}

    # 2. Load Excel Data
    sheets = load_excel_sheets()
    
    # Find the correct sheet name (handling spaces)
    target_sheet = None
    for name in sheets.keys():
        if name.strip() == "Final Gene Score":
            target_sheet = name
            break
            
    if not target_sheet:
        # If sheet is missing, return 0 or handle error. 
        # Since this is a utility, maybe raising error is fine, or return 0.
        # Following original logic of raising exception but simplified here to return 0 with error in dict?
        # Or better raise ValueError.
        raise ValueError("Final Gene Score sheet not found in data set")
        
    rows = sheets[target_sheet]
    if not rows:
        return {"score": 0.0}
        
    headers = [str(h).strip() for h in rows[0]]
    
    # helper to find index by list of candidates
    def find_col_index(headers_list, candidates):
        headers_lower = [h.lower() for h in headers_list]
        for candidate in candidates:
            cand_lower = candidate.lower()
            # Try exact match first
            try:
                return headers_lower.index(cand_lower)
            except ValueError:
                continue
        # Try starts/ends with
        for i, h in enumerate(headers_lower):
             for candidate in candidates:
                 cand_lower = candidate.lower()
                 if h == cand_lower or h.startswith(cand_lower) or h.endswith(cand_lower):
                     return i
        return -1

    idx_gene = find_col_index(headers, ["Gene Symbol", "Gene", "Symbol"])
    idx_score = find_col_index(headers, ["Final Score", "Total Score", "Score"])

    # If still not found, try fallback indices based on found structure (0 and 1 from debug output)
    if idx_gene == -1: idx_gene = 0
    if idx_score == -1: 
        # checking if we have at least 2 columns
        if len(headers) >= 2:
            idx_score = 1
        else:
            idx_score = 4 # legacy fallback

    # 3. Sum scores
    total_score = 0.0
    genes_found = []
    
    # Create lookup map (Gene -> Score)
    gene_score_map = {}
    for row in rows[1:]:
        if len(row) > idx_score:
            g_sym = str(row[idx_gene]).strip().upper()
            val = row[idx_score]
            # Ensure val is numeric
            if val is not None:
                try:
                    score_val = float(val)
                    gene_score_map[g_sym] = score_val
                except (ValueError, TypeError):
                    continue

    for bg in scored_genes:
        if bg in gene_score_map:
            total_score += gene_score_map[bg]
            genes_found.append(bg)

    final_result = total_score / DIVISOR

    return {
        "score": final_result,
        "total_sum": total_score,
        "offset_divisor": DIVISOR,
        "genes_counted": genes_found
    }
