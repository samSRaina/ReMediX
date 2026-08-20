import math

from ..clients import creeds_client


ACTION_BY_ACTIVITY_TYPE = {
    "IC50": "INHIBITION",
    "KI": "INHIBITION",
    "AC50": "ACTIVATION",
}


def _round_metric(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _resolve_drug_action(activity_types: list[str]) -> str:
    actions = {
        ACTION_BY_ACTIVITY_TYPE.get(str(activity_type or "").strip().upper())
        for activity_type in activity_types
    }
    actions.discard(None)
    if len(actions) == 1:
        return list(actions)[0]
    return "UNKNOWN"


def _activity_strength_from_nm(best_nm_value: float | None) -> float:
    if best_nm_value is None or best_nm_value <= 0:
        return 0.0
    signal = 1.0 / (1.0 + math.log10(best_nm_value / 100.0))
    return _clip(signal, 0.0, 1.0)


def _classify_interaction(disease_direction: str, drug_action: str) -> str:
    if disease_direction == "UP" and drug_action == "INHIBITION":
        return "BENEFICIAL"
    if disease_direction == "DOWN" and drug_action == "ACTIVATION":
        return "BENEFICIAL"
    if disease_direction == "UP" and drug_action == "ACTIVATION":
        return "HARMFUL"
    if disease_direction == "DOWN" and drug_action == "INHIBITION":
        return "HARMFUL"
    return "UNRESOLVED"


def calculate_remedix_score(aggregated_targets: list[dict], disease: str) -> dict:
    disease_consensus = creeds_client.build_disease_direction_consensus(disease)
    disease_records = disease_consensus.get("gene_records", []) or []
    disease_lookup = {row["gene"]: row for row in disease_records}
    disease_total = int(disease_consensus.get("disease_total", 0) or 0)

    target_lookup = {
        str(row.get("gene_symbol", "")).strip().upper(): row
        for row in (aggregated_targets or [])
        if str(row.get("gene_symbol", "")).strip()
    }
    overlap_genes = sorted(set(disease_lookup.keys()) & set(target_lookup.keys()))

    gene_records = []
    beneficial_sum = 0.0
    harmful_sum = 0.0

    for gene in overlap_genes:
        disease_row = disease_lookup[gene]
        target_row = target_lookup[gene]
        measurements = target_row.get("measurements", []) or []
        activity_types = [str(item.get("activity_type", "")).strip().upper() for item in measurements if item.get("activity_type")]
        drug_action = _resolve_drug_action(activity_types)

        best_nm_value = None
        for measurement in measurements:
            value_nm = measurement.get("activity_value_nm")
            if isinstance(value_nm, (int, float)):
                parsed = float(value_nm)
                if parsed > 0 and (best_nm_value is None or parsed < best_nm_value):
                    best_nm_value = parsed

        activity_strength = _activity_strength_from_nm(best_nm_value)
        disease_direction = str(disease_row.get("disease_direction", "AMBIGUOUS")).upper()
        classification = _classify_interaction(disease_direction, drug_action)

        gene_contribution = 0.0
        if classification in {"BENEFICIAL", "HARMFUL"} and disease_direction in {"UP", "DOWN"}:
            dc = float(disease_row.get("dc", 0.0) or 0.0)
            gene_contribution = dc * (0.7 + 0.3 * activity_strength)

        if classification == "BENEFICIAL":
            beneficial_sum += gene_contribution
        elif classification == "HARMFUL":
            harmful_sum += gene_contribution

        gene_records.append(
            {
                "gene": gene,
                "U": int(disease_row.get("U", 0) or 0),
                "D": int(disease_row.get("D", 0) or 0),
                "disease_direction": disease_direction,
                "dc": _round_metric(float(disease_row.get("dc", 0.0) or 0.0)),
                "drug_action": drug_action,
                "activity_type": sorted(set(activity_types)),
                "activity_strength": _round_metric(activity_strength),
                "classification": classification,
                "gene_contribution": _round_metric(gene_contribution),
                "activity_value_nm": _round_metric(best_nm_value) if best_nm_value is not None else None,
                "supporting_measurements": len(measurements),
                "target_chembl_ids": target_row.get("target_chembl_ids", []),
                "uniprot_ids": target_row.get("uniprot_ids", []),
            }
        )

    net_signal = beneficial_sum - harmful_sum
    divisor = float(disease_total) if disease_total > 0 else 1.0
    benefit_coverage = beneficial_sum / divisor
    harm_coverage = harmful_sum / divisor
    net_coverage = net_signal / divisor
    target_coverage = (len(overlap_genes) / divisor) if disease_total > 0 else 0.0
    raw_score = 100.0 * net_coverage
    public_score = _clip(raw_score, 0.0, 100.0)

    return {
        "disease": disease,
        "disease_total": disease_total,
        "disease_gene_set": disease_consensus.get("disease_gene_set", []),
        "target_gene_total": len(target_lookup),
        "matched_target_count": len(overlap_genes),
        "beneficial_signal": _round_metric(beneficial_sum),
        "harmful_signal": _round_metric(harmful_sum),
        "net_therapeutic_signal": _round_metric(net_signal),
        "benefit_coverage": _round_metric(benefit_coverage),
        "benefit_coverage_percent": _round_metric(benefit_coverage * 100.0),
        "harm_coverage": _round_metric(harm_coverage),
        "harm_coverage_percent": _round_metric(harm_coverage * 100.0),
        "net_coverage": _round_metric(net_coverage),
        "net_coverage_percent": _round_metric(net_coverage * 100.0),
        "target_coverage": _round_metric(target_coverage),
        "target_coverage_percent": _round_metric(target_coverage * 100.0),
        "raw_remedix_score": _round_metric(raw_score),
        "remedix_score": _round_metric(public_score),
        "directional_evidence": {
            "model": "CREEDS Direction Consensus (DC)",
            "source_entry_count": disease_consensus.get("source_entry_count", 0),
            "matched_genes": len(overlap_genes),
        },
        "gene_records": gene_records,
    }
