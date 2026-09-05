import logging
import math
import statistics

from ..clients import creeds_client
from .scoring_policies import ScoringPolicies

logger = logging.getLogger(__name__)


ACTION_BY_ACTIVITY_TYPE = {
    "IC50": "INHIBITION",
    "KI": "INHIBITION",
    "AC50": "ACTIVATION",
}

# Contribution weight split: biological consensus 70%, pharmacological potency 30%.
CONSENSUS_WEIGHT = 0.7
POTENCY_WEIGHT = 0.3


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


def _valid_nm_values(measurements: list[dict]) -> list[float]:
    """All positive, finite nM values from a gene's measurements."""
    values = []
    for measurement in measurements or []:
        value_nm = measurement.get("activity_value_nm")
        if isinstance(value_nm, (int, float)) and not isinstance(value_nm, bool):
            parsed = float(value_nm)
            if math.isfinite(parsed) and parsed > 0:
                values.append(parsed)
    return values


def _representative_nm(measurements: list[dict], policies: ScoringPolicies) -> tuple[float | None, int]:
    """Collapse a gene's valid nM measurements into one representative value.

    Returns (representative_nm, valid_measurement_count). representative_nm is
    None when no measurement carries a valid nM value (the caller then applies
    the missing-value policy).
    """
    values = _valid_nm_values(measurements)
    if not values:
        return None, 0
    if policies.assay_aggregation == "min":
        return min(values), len(values)
    if policies.assay_aggregation == "mean":
        return sum(values) / len(values), len(values)
    return statistics.median(values), len(values)  # default: median


def _activity_strength_from_nm(
    nm_value: float | None,
    policies: ScoringPolicies,
) -> tuple[float, bool]:
    """Pharmacological activity strength, 0-1, plus a defaulted flag.

    Model "log_ramp" (spec v2):  max(0, min(1, 1 - (log10(nM) - 1) / 3))
      -> 1 nM = 1.0, 10 nM = 1.0, 100 nM = 2/3, 1 uM = 1/3, >=10 uM = 0.
    Model "legacy_inverse_log" (kept for A/B reproducibility):
      1 / (1 + log10(nM / 100)) — with the denominator floored at a positive
      epsilon so the historical 10 nM ZeroDivisionError can never recur.

    A missing/invalid nM value (nm_value is None or <= 0) yields the policy's
    missing_activity_strength and defaulted=True.
    """
    if nm_value is None or nm_value <= 0:
        return float(policies.missing_activity_strength), True

    if policies.activity_strength_model == "legacy_inverse_log":
        denominator = 1.0 + math.log10(nm_value / 100.0)
        if denominator <= 0.0:
            # Historic crash guard: old formula hit exactly 0 at 10 nM.
            return 1.0, False
        return _clip(1.0 / denominator, 0.0, 1.0), False

    # Spec v2 bounded log ramp.
    strength = 1.0 - (math.log10(nm_value) - 1.0) / 3.0
    return _clip(strength, 0.0, 1.0), False


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


def calculate_remedix_score(
    aggregated_targets: list[dict],
    disease: str,
    policies: ScoringPolicies | None = None,
) -> dict:
    """Execute Steps 6-21 of the ReMediX pipeline under the given policies.

    aggregated_targets comes from ChEMBLClient.get_aggregated_targets_by_inchikey
    (gene-bucketed measurements). policies defaults to ScoringPolicies() (spec
    v2); the effective policy set is echoed in the response under "policies".
    """
    if policies is None:
        policies = ScoringPolicies()

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

        # Activity types for traceability: original ChEMBL spelling when
        # available (Step 21), upper-cased for action resolution.
        activity_types = [
            str(item.get("activity_type", "")).strip().upper()
            for item in measurements
            if item.get("activity_type")
        ]
        original_types = sorted({
            str(item.get("standard_type") or item.get("activity_type") or "")
            for item in measurements
            if (item.get("standard_type") or item.get("activity_type"))
        })
        drug_action = _resolve_drug_action(activity_types)

        representative_nm, valid_count = _representative_nm(measurements, policies)
        activity_strength, strength_defaulted = _activity_strength_from_nm(representative_nm, policies)

        disease_direction = str(disease_row.get("disease_direction", "AMBIGUOUS")).upper()
        classification = _classify_interaction(disease_direction, drug_action)

        gene_contribution = 0.0
        if classification in {"BENEFICIAL", "HARMFUL"} and disease_direction in {"UP", "DOWN"}:
            dc = float(disease_row.get("dc", 0.0) or 0.0)
            gene_contribution = dc * (CONSENSUS_WEIGHT + POTENCY_WEIGHT * activity_strength)

        if classification == "BENEFICIAL":
            beneficial_sum += gene_contribution
        elif classification == "HARMFUL":
            harmful_sum += gene_contribution

        record = {
            "gene": gene,
            "U": int(disease_row.get("U", 0) or 0),
            "D": int(disease_row.get("D", 0) or 0),
            "disease_direction": disease_direction,
            "dc": _round_metric(float(disease_row.get("dc", 0.0) or 0.0)),
            "drug_action": drug_action,
            "activity_type": sorted(set(t for t in original_types if t)),
            "activity_strength": _round_metric(activity_strength),
            "activity_strength_defaulted": strength_defaulted,
            "representative_value_nm": _round_metric(representative_nm) if representative_nm is not None else None,
            "representative_aggregation": policies.assay_aggregation if valid_count else None,
            "valid_measurement_count": valid_count,
            "supporting_measurements": len(measurements),
            "classification": classification,
            "gene_contribution": _round_metric(gene_contribution),
            "target_chembl_ids": target_row.get("target_chembl_ids", []),
            "uniprot_ids": target_row.get("uniprot_ids", []),
        }
        if strength_defaulted:
            logger.info(
                "Gene %s: no valid nM measurement (%d measurements, %d usable) -> "
                "activity_strength defaulted to %s",
                gene, len(measurements), valid_count, policies.missing_activity_strength,
            )

        # Step 8: U == D -> AMBIGUOUS + UNRESOLVED, contribution 0 (matrix row
        # kept under the default "unresolved" policy). Under "exclude" the row
        # is dropped from the matrix entirely (still counts as matched).
        if disease_direction == "AMBIGUOUS" and policies.ambiguous_policy == "exclude":
            continue
        gene_records.append(record)

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
        "policies": policies.describe(),
        "directional_evidence": {
            "model": "CREEDS Direction Consensus (DC)",
            "source_entry_count": disease_consensus.get("source_entry_count", 0),
            "matched_genes": len(overlap_genes),
        },
        "gene_records": gene_records,
    }
