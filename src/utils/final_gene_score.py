from __future__ import annotations

import json
import math
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import openpyxl

from ..clients import chembl_client, creeds_client

_EXCLUDED_SHEETS = ["Reactome"]
_AMBIGUITY_THRESHOLD = 1.2
_PROMISCUITY_COEFFICIENT = 0.1
_STANDARD_TYPE_EFFECT = {
    "IC50": "INHIBITOR",
    "KI": "INHIBITOR",
    "AC50": "ACTIVATOR",
    "EC50": "ACTIVATOR",
}
_STANDARD_TYPE_PRIORITY = {"IC50": 0, "KI": 1, "AC50": 2, "EC50": 3}
_WEIGHT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "gene_weight_config.json"


@lru_cache(maxsize=1)
def load_excel_sheets() -> dict[str, list[list]]:
    """Read all non-excluded sheets once and cache them."""

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
            while cleaned and cleaned[-1] is None:
                cleaned.pop()
            rows.append(cleaned)
        result[sheet_name] = rows

    return result


@lru_cache(maxsize=1)
def _load_weight_config() -> dict:
    if not _WEIGHT_CONFIG_PATH.exists():
        return {"default": {}, "disease_overrides": {}}
    with open(_WEIGHT_CONFIG_PATH, "r") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return {"default": {}, "disease_overrides": {}}
    return payload


@lru_cache(maxsize=64)
def _get_disease_lookup_with_denominator(disease: str) -> tuple[dict[str, dict], float]:
    return creeds_client._build_disease_signature_lookup(disease)


def _normalize_standard_type(raw_type: str | None) -> str:
    return str(raw_type or "").strip().upper()


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_creeds_direction(gene: str, perturbation_index: dict[str, dict]) -> dict:
    counts = perturbation_index.get(gene)
    if not counts:
        return {
            "up_count": 0,
            "down_count": 0,
            "ratio": 0.0,
            "ambiguous": True,
            "direction": None,
            "skip_reason": "NO_CREEDS_DATA",
        }

    up_count = int(counts.get("up_count", 0) or 0)
    down_count = int(counts.get("down_count", 0) or 0)
    minimum = min(up_count, down_count)
    maximum = max(up_count, down_count)
    if minimum > 0:
        ratio = float(maximum) / float(minimum)
    elif maximum > 0:
        ratio = float("inf")
    else:
        ratio = 0.0

    ambiguous = ratio < _AMBIGUITY_THRESHOLD
    if up_count == down_count:
        ambiguous = True

    direction = None if ambiguous else ("UP" if up_count > down_count else "DOWN")
    skip_reason = "AMBIGUOUS_CREEDS_RATIO" if ambiguous else None
    return {
        "up_count": up_count,
        "down_count": down_count,
        "ratio": ratio,
        "ambiguous": ambiguous,
        "direction": direction,
        "skip_reason": skip_reason,
    }


def _pick_best_activity_per_gene(activities: list[dict]) -> dict[str, dict]:
    supported: dict[str, dict] = {}
    for row in activities or []:
        gene = str(row.get("gene_symbol") or "").strip().upper()
        if not gene or gene == "--":
            continue

        standard_type = _normalize_standard_type(row.get("standard_type"))
        if standard_type not in _STANDARD_TYPE_EFFECT:
            continue

        potency = _to_float(row.get("standard_value"))
        if potency is None:
            continue

        current = supported.get(gene)
        candidate = {
            "gene": gene,
            "standard_type": standard_type,
            "standard_value": potency,
            "drug_effect": _STANDARD_TYPE_EFFECT[standard_type],
        }
        if current is None:
            supported[gene] = candidate
            continue

        if potency < current["standard_value"]:
            supported[gene] = candidate
            continue

        if potency == current["standard_value"]:
            if _STANDARD_TYPE_PRIORITY.get(standard_type, 99) < _STANDARD_TYPE_PRIORITY.get(
                current["standard_type"], 99
            ):
                supported[gene] = candidate

    return supported


def _get_gene_weight(disease: str, gene: str, weight_config: dict) -> float:
    disease_key = str(disease or "").strip().lower()
    default_weights = weight_config.get("default", {}) if isinstance(weight_config, dict) else {}
    disease_overrides = weight_config.get("disease_overrides", {}) if isinstance(weight_config, dict) else {}
    disease_weights = disease_overrides.get(disease_key, {}) if isinstance(disease_overrides, dict) else {}

    value = disease_weights.get(gene, default_weights.get(gene, 1.0))
    try:
        weight = float(value)
    except (TypeError, ValueError):
        weight = 1.0
    return weight if weight >= 0 else 0.0


def _categorize_score(final_score: float) -> str:
    if final_score > 0.05:
        return "High"
    if 0.02 <= final_score <= 0.05:
        return "Moderate"
    return "Low"


def _calculate_promiscuity_penalty(target_count: int) -> float:
    if target_count <= 1:
        return 1.0
    return 1.0 / (1.0 + (_PROMISCUITY_COEFFICIENT * math.log(target_count)))


def calculate_final_score(inchikey: str, disease: str) -> dict:
    if not disease or not disease.strip():
        raise ValueError("Disease parameter is required for final score calculation")
    if not inchikey or not inchikey.strip():
        raise ValueError("InChIKey parameter is required for final score calculation")

    chembl = chembl_client.ChEMBLClient()
    activities = chembl.get_by_inchikey(inchikey.strip())
    if not activities:
        raise ValueError(f"No ChEMBL bioactivity data found for '{inchikey}'")

    selected_by_gene = _pick_best_activity_per_gene(activities)
    unique_genes = sorted(selected_by_gene.keys())
    if not unique_genes:
        return {
            "drug": inchikey,
            "disease": disease,
            "numerator": 0.0,
            "denominator": round(_get_disease_lookup_with_denominator(disease)[1], 6),
            "raw_score": 0.0,
            "promiscuity_penalty": 1.0,
            "target_count": 0,
            "final_score": 0.0,
            "category": "Low",
            "beneficial_genes": [],
            "gene_breakdown": [],
        }

    perturbation_index = creeds_client._load_single_gene_perturbation_index()
    disease_lookup, denominator = _get_disease_lookup_with_denominator(disease)
    weight_config = _load_weight_config()

    numerator = 0.0
    beneficial_genes = []
    breakdown = []

    for gene in unique_genes:
        activity = selected_by_gene[gene]
        creeds_data = _resolve_creeds_direction(gene, perturbation_index)
        row = {
            "gene": gene,
            "standard_type": activity["standard_type"],
            "drug_effect": activity["drug_effect"],
            "up_count": creeds_data["up_count"],
            "down_count": creeds_data["down_count"],
            "creeds_ratio": None if math.isinf(creeds_data["ratio"]) else round(creeds_data["ratio"], 4),
            "creeds_direction": creeds_data["direction"],
            "disease_direction_source": None,
            "disease_direction": None,
            "disease_signature_score": None,
            "weight": 1.0,
            "classification": "AMBIGUOUS" if creeds_data["ambiguous"] else "UNCLASSIFIED",
            "contribution": 0.0,
            "skip_reason": creeds_data["skip_reason"],
        }

        if creeds_data["ambiguous"]:
            breakdown.append(row)
            continue

        disease_hit = disease_lookup.get(gene)
        if disease_hit:
            disease_direction = str(disease_hit["direction"]).upper()
            disease_score = float(disease_hit["score"])
            row["disease_direction_source"] = "DISEASE_SIGNATURE"
            row["disease_direction"] = disease_direction
            row["disease_signature_score"] = round(disease_score, 6)
        else:
            disease_direction = creeds_data["direction"]
            row["disease_direction_source"] = "CREEDS_BACKUP"
            row["disease_direction"] = disease_direction
            row["skip_reason"] = "NO_DISEASE_SIGNATURE_SCORE"
            row["classification"] = "AMBIGUOUS"
            breakdown.append(row)
            continue

        drug_effect = activity["drug_effect"]
        beneficial = (disease_direction == "UP" and drug_effect == "INHIBITOR") or (
            disease_direction == "DOWN" and drug_effect == "ACTIVATOR"
        )

        if not beneficial:
            row["classification"] = "HARMFUL"
            row["skip_reason"] = "HARMFUL_DIRECTIONAL_MATCH"
            breakdown.append(row)
            continue

        weight = _get_gene_weight(disease, gene, weight_config)
        contribution = disease_score * weight
        row["weight"] = round(weight, 6)
        row["contribution"] = round(contribution, 6)
        row["classification"] = "BENEFICIAL"
        row["skip_reason"] = None
        numerator += contribution
        beneficial_genes.append({"gene": gene, "contribution": round(contribution, 6)})
        breakdown.append(row)

    if denominator <= 0:
        raise ValueError(f"Disease '{disease}' has invalid denominator (<= 0)")

    raw_score = numerator / denominator
    target_count = len(unique_genes)
    penalty = _calculate_promiscuity_penalty(target_count)
    final_score = min(raw_score * penalty * 10.0, 1.0)

    return {
        "drug": inchikey,
        "disease": disease,
        "numerator": round(numerator, 6),
        "denominator": round(denominator, 6),
        "raw_score": round(raw_score, 6),
        "promiscuity_penalty": round(penalty, 6),
        "target_count": target_count,
        "final_score": round(final_score, 6),
        "category": _categorize_score(final_score),
        "beneficial_genes": beneficial_genes,
        "gene_breakdown": breakdown,
    }
