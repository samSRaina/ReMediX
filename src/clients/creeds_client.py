from pathlib import Path
import json
import math
from functools import lru_cache


DISEASE_SIG = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signatures-v1.0.json'
SINGLE_DRUG_PERTURBATION = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'single_drug_perturbations-v1.0.json'
DISEASE_SIGNATURE_TABLE = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signature_table.json'
SCORING_CALIBRATION = Path(__file__).parent.parent / 'config' / 'scoring_calibration.json'
RATIO_THRESHOLD = 1.2
# Confidence is blended from coverage and vote balance.
# Base keeps confidence non-zero when evidence exists; weight increases confidence as votes become one-sided.
CONFIDENCE_BALANCE_BASE = 0.5
CONFIDENCE_BALANCE_WEIGHT = 0.5


@lru_cache(maxsize=1)
def _load_disease_signature_dataset() -> list:
    with open(DISEASE_SIG, 'r') as file:
        return json.load(file)


@lru_cache(maxsize=1)
def _load_drug_perturbation_dataset() -> list:
    with open(SINGLE_DRUG_PERTURBATION, 'r') as file:
        return json.load(file)


@lru_cache(maxsize=1)
def _load_scoring_calibration() -> dict:
    if not SCORING_CALIBRATION.exists():
        return {}
    with open(SCORING_CALIBRATION, 'r') as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}


def _get_disease_signature_entry(disease: str) -> dict:
    disease_key = (disease or '').strip().lower()
    for entry in _load_disease_signature_dataset():
        if str(entry.get('disease_name', '')).strip().lower() == disease_key:
            return entry
    raise ValueError(f"Disease '{disease}' not found in CREEDS signatures")


def get_disease_signatures(disease) -> list:
    entry = _get_disease_signature_entry(disease)
    return entry.get('up_genes', []) + entry.get('down_genes', [])


def build_disease_signature_table(disease: str) -> dict:
    """Build a flat table-friendly representation for one disease signature."""
    entry = _get_disease_signature_entry(disease)

    rows = []
    for gene, score in entry.get('up_genes', []):
        rows.append([gene, score, 'up'])
    for gene, score in entry.get('down_genes', []):
        rows.append([gene, score, 'down'])

    return {
        'disease': disease,
        'headers': ['Gene Symbol', 'Score', 'Direction'],
        'rows': rows,
    }


def export_disease_signature_table(disease: str, output_path: Path = DISEASE_SIGNATURE_TABLE) -> dict:
    """Write the normalized disease signature table to JSON and return the payload."""
    payload = build_disease_signature_table(disease)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as file:
        json.dump(payload, file, indent=2)

    payload['export_file'] = str(output_path)
    return payload


def _normalize_direction(direction: str) -> str | None:
    normalized = str(direction or '').strip().upper()
    if normalized in {'UP', 'DOWN'}:
        return normalized
    return None


def _extract_gene_symbol(gene_row) -> str:
    """Extract a gene symbol from common CREEDS row shapes."""
    if isinstance(gene_row, (list, tuple)) and gene_row:
        return str(gene_row[0] or '').strip().upper()
    if isinstance(gene_row, dict):
        return str(gene_row.get('gene', '') or '').strip().upper()
    return str(gene_row or '').strip().upper()


@lru_cache(maxsize=1)
def _load_single_gene_perturbation_index() -> dict[str, dict[str, int]]:
    """
    Build an index of target gene -> aggregated up/down counts across
    matching single-drug perturbation signatures.
    """
    index: dict[str, dict[str, int]] = {}

    for entry in _load_drug_perturbation_dataset():
        if not isinstance(entry, dict):
            continue

        up_genes = entry.get('up_genes', []) or []
        down_genes = entry.get('down_genes', []) or []

        up_count = len(up_genes)
        down_count = len(down_genes)

        if up_count == 0 and down_count == 0:
            continue

        candidate_targets = set()
        for row in up_genes:
            gene = _extract_gene_symbol(row)
            if gene:
                candidate_targets.add(gene)
        for row in down_genes:
            gene = _extract_gene_symbol(row)
            if gene:
                candidate_targets.add(gene)

        for target in candidate_targets:
            bucket = index.setdefault(target, {'up_count': 0, 'down_count': 0})
            bucket['up_count'] += up_count
            bucket['down_count'] += down_count

    return index


def _compute_ratio(up_count: int, down_count: int) -> float:
    numerator = max(up_count, down_count)
    denominator = min(up_count, down_count)

    if numerator == 0:
        return 0.0
    # Keep response JSON-safe and deterministic; avoid Infinity payloads.
    safe_denominator = denominator if denominator > 0 else 1
    return float(numerator) / float(safe_denominator)


def _round_metric(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_disease_signature_lookup(disease: str) -> tuple[dict[str, dict], float]:
    """Return disease gene lookup keyed by symbol and total absolute signature score."""
    entry = _get_disease_signature_entry(disease)
    lookup: dict[str, dict] = {}
    total_abs_score = 0.0

    for direction_key, direction in (('up_genes', 'UP'), ('down_genes', 'DOWN')):
        for row in entry.get(direction_key, []) or []:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue

            gene = str(row[0] or '').strip().upper()
            score = _to_float(row[1])
            if not gene or score is None:
                continue

            abs_score = abs(score)
            total_abs_score += abs_score
            lookup[gene] = {
                'gene': gene,
                'direction': direction,
                'score': score,
                'abs_score': abs_score,
            }

    return lookup, total_abs_score


def _interpret_final_score(score: float) -> str:
    thresholds = _load_scoring_calibration().get('interpretation_thresholds', {})
    try:
        strong_candidate_min = float(thresholds.get('strong_candidate_min', 0.60))
    except (TypeError, ValueError):
        strong_candidate_min = 0.60
    try:
        mixed_effect_min = float(thresholds.get('mixed_effect_min', 0.40))
    except (TypeError, ValueError):
        mixed_effect_min = 0.40

    strong_candidate_min = min(max(strong_candidate_min, 0.0), 1.0)
    mixed_effect_min = min(max(mixed_effect_min, 0.0), strong_candidate_min)

    if score >= strong_candidate_min:
        return 'strong candidate (mostly beneficial)'
    if score >= mixed_effect_min:
        return 'mixed effect'
    return 'likely harmful'


def _target_reliability_weight(up_count: int, down_count: int, ratio: float, ratio_threshold: float) -> float:
    total = up_count + down_count
    if total <= 0:
        return 0.0

    imbalance = abs(up_count - down_count) / float(total)
    if ratio_threshold <= 1.0:
        ratio_strength = 1.0 if ratio > 1.0 else 0.0
    else:
        ratio_strength = (ratio - 1.0) / (ratio_threshold - 1.0)
        ratio_strength = min(max(ratio_strength, 0.0), 1.0)

    combined_strength = (imbalance + ratio_strength) / 2.0
    return _round_metric(0.25 + (0.75 * combined_strength))


def _weighted_disease_gene_mass(abs_score: float, beneficial_votes: float, harmful_votes: float) -> float:
    total_votes = beneficial_votes + harmful_votes
    if total_votes <= 0:
        return 0.0

    vote_margin = abs(beneficial_votes - harmful_votes) / total_votes
    # Additive smoothing (denominator +2) dampens very low-support vote totals.
    support = total_votes / (total_votes + 2.0)
    # Square-root (sublinear) scaling keeps high-magnitude signature genes influential
    # while preventing a few extreme scores from dominating mass.
    magnitude = math.sqrt(max(abs_score, 0.0))
    weighted_mass = magnitude * vote_margin * support
    return _round_metric(weighted_mass)


def _match_perturbations_against_disease(
    drug_perturbations: list,
    disease_map: dict[str, float],
) -> tuple[int, int, set[str]]:
    """Return beneficial/harmful counts and beneficial disease genes for one target gene."""
    beneficial = 0
    harmful = 0
    beneficial_disease_genes: set[str] = set()

    for drug_gene_entry in drug_perturbations or []:
        if not isinstance(drug_gene_entry, (list, tuple)) or len(drug_gene_entry) < 2:
            continue

        disease_gene = str(drug_gene_entry[0]).strip().lower()
        drug_score = _to_float(drug_gene_entry[1])
        disease_score = disease_map.get(disease_gene)

        if not disease_gene or drug_score is None or disease_score is None:
            continue

        if (drug_score < 0 < disease_score) or (drug_score > 0 > disease_score):
            beneficial += 1
            beneficial_disease_genes.add(disease_gene.upper())
        elif (drug_score < 0 and disease_score < 0) or (drug_score > 0 and disease_score > 0):
            harmful += 1

    return beneficial, harmful, beneficial_disease_genes


def _collect_disease_gene_votes(
    drug_perturbations: list,
    disease_lookup: dict[str, dict],
) -> dict[str, dict[str, int]]:
    """
    Collect beneficial/harmful vote counts per disease gene from one target gene's perturbations.
    A disease gene is beneficial for one vote when drug direction is opposite to disease direction.
    """
    votes: dict[str, dict[str, int]] = {}

    for drug_gene_entry in drug_perturbations or []:
        if not isinstance(drug_gene_entry, (list, tuple)) or len(drug_gene_entry) < 2:
            continue

        gene = str(drug_gene_entry[0] or '').strip().upper()
        drug_score = _to_float(drug_gene_entry[1])
        if not gene or drug_score is None or drug_score == 0:
            continue

        disease_hit = disease_lookup.get(gene)
        if not disease_hit:
            continue

        perturb_direction = 'UP' if drug_score > 0 else 'DOWN'
        disease_direction = disease_hit['direction']

        bucket = votes.setdefault(gene, {'beneficial_votes': 0, 'harmful_votes': 0})
        if perturb_direction != disease_direction:
            bucket['beneficial_votes'] += 1
        else:
            bucket['harmful_votes'] += 1

    return votes


def compute_beneficial_score(
    drug_targets: list[str],
    disease_signature: dict[str, str],
    perturbation_data: dict[str, list[dict[str, str]]],
    ratio_threshold: float = 1.2,
) -> dict:
    """
    Score a drug by checking if perturbations reverse disease direction.

    Rules:
    - Use only targets present in perturbation_data.
    - Opposite direction => beneficial, same direction => harmful.
    - ratio = beneficial / max(harmful, 1); discard gene when ratio < ratio_threshold.
    - gene_score = beneficial - harmful for retained genes.
    - total_score sums positive gene_score values only.
    """
    if ratio_threshold <= 0:
        raise ValueError('ratio_threshold must be > 0')

    disease_map = {
        str(gene).strip().upper(): direction
        for gene, raw_direction in (disease_signature or {}).items()
        if (direction := _normalize_direction(raw_direction)) is not None
    }

    perturbation_map = {
        str(target).strip().upper(): (records or [])
        for target, records in (perturbation_data or {}).items()
    }

    total_score = 0
    genes_used = 0
    genes_filtered_out = 0
    details = []

    for raw_target in drug_targets or []:
        target = str(raw_target or '').strip().upper()
        if not target or target not in perturbation_map:
            continue

        beneficial_count = 0
        harmful_count = 0

        for effect in perturbation_map[target]:
            if not isinstance(effect, dict):
                continue

            downstream_gene = str(effect.get('gene', '')).strip().upper()
            perturb_direction = _normalize_direction(effect.get('direction'))
            if not downstream_gene or not perturb_direction:
                continue

            disease_direction = disease_map.get(downstream_gene)
            if not disease_direction:
                continue

            if perturb_direction != disease_direction:
                beneficial_count += 1
            else:
                harmful_count += 1

        ratio = beneficial_count / max(harmful_count, 1)
        if ratio < ratio_threshold:
            genes_filtered_out += 1
            continue

        gene_score = beneficial_count - harmful_count
        details.append({
            'gene': target,
            'beneficial': beneficial_count,
            'harmful': harmful_count,
            'ratio': ratio,
            'score': gene_score,
        })

        if gene_score > 0:
            total_score += gene_score
            genes_used += 1

    return {
        'total_score': total_score,
        'genes_used': genes_used,
        'genes_filtered_out': genes_filtered_out,
        'details': details,
    }


class CreedsClient:
    def __init__(self, uniprot_accession_gene: str) :
        self.uniprot_gene = uniprot_accession_gene

    def get_single_drug_perturbations(self) -> list:
        single_gene_perturbations = _load_drug_perturbation_dataset()

        response_dataset = []
        target_gene_lower = str(self.uniprot_gene).strip().lower()

        for entry in single_gene_perturbations:
            up_genes = entry.get("up_genes", [])
            down_genes = entry.get("down_genes", [])

            # Check if target gene is present in this experiment (in up or down lists)
            target_matches_up = any(str(g[0]).strip().lower() == target_gene_lower for g in up_genes)
            target_matches_down = any(str(g[0]).strip().lower() == target_gene_lower for g in down_genes)

            # If target gene is perturbed in this experiment, include the ENTIRE signature
            if target_matches_up or target_matches_down:
                response_dataset.extend(up_genes)
                response_dataset.extend(down_genes)

        return response_dataset

    def match_genes(self, disease_genes: list, drug_perturbations: list):
        disease_map = {}
        for row in disease_genes or []:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            gene = str(row[0]).strip().lower()
            score = _to_float(row[1])
            if gene and score is not None:
                disease_map[gene] = score

        beneficial, harmful, _ = _match_perturbations_against_disease(drug_perturbations, disease_map)

        return f"beneficial: {beneficial}", f"harmful: {harmful}"


def match_gene_set(gene_list: list[str], disease: str | None = None) -> dict:
    """
    Repurposing scoring with uncertainty-aware aggregation:
    1) Classify target genes by CREEDS perturbation direction with soft reliability weights.
    2) Aggregate weighted beneficial/harmful votes per disease gene.
    3) Score only beneficial vs harmful evidence; ties/no-vote are tracked as uncertain.
    """
    if not disease or not disease.strip():
        raise ValueError('Disease parameter is required')

    perturbation_index = _load_single_gene_perturbation_index()
    disease_lookup, disease_signature_total_abs_score = _build_disease_signature_lookup(disease)

    seen = set()
    input_genes = []
    for raw_gene in gene_list or []:
        gene = str(raw_gene or '').strip()
        if not gene:
            continue
        key = gene.upper()
        if key in seen:
            continue
        seen.add(key)
        input_genes.append(gene)

    results = []
    up_genes = []
    down_genes = []
    ambiguous_targets = []
    not_found_genes = []
    no_disease_overlap_genes = []
    disease_gene_vote_map: dict[str, dict[str, float]] = {
        gene: {'beneficial_votes': 0.0, 'harmful_votes': 0.0}
        for gene in disease_lookup
    }

    beneficial_sum = 0.0
    harmful_sum = 0.0
    uncertain_sum = 0.0
    classified_gene_count = 0
    matched_gene_count = 0
    beneficial_gene_count = 0
    harmful_gene_count = 0
    uncertain_gene_count = 0

    for gene in input_genes:
        key = gene.upper()
        counts = perturbation_index.get(key)
        if not counts:
            not_found_genes.append(gene)
            continue

        up_count = int(counts.get('up_count', 0) or 0)
        down_count = int(counts.get('down_count', 0) or 0)
        ratio = _compute_ratio(up_count, down_count)
        is_ambiguous = up_count == down_count or ratio < RATIO_THRESHOLD
        target_weight = _target_reliability_weight(up_count, down_count, ratio, RATIO_THRESHOLD)

        row = {
            'gene': gene,
            'up_count': up_count,
            'down_count': down_count,
            'ratio': _round_metric(ratio),
            'target_weight': target_weight,
            'classification': 'AMBIGUOUS',
            'direction': 'AMBIGUOUS',
            'disease_direction': None,
            'disease_score': None,
            'common_disease_gene_count': 0,
            'effect': 'LOW_CONFIDENCE',
            'reason': 'AMBIGUOUS_RATIO_OR_TIE' if is_ambiguous else 'CLEAR_DIRECTION',
        }

        if not is_ambiguous:
            direction = 'UP' if up_count > down_count else 'DOWN'
            row['classification'] = direction
            row['direction'] = direction
            classified_gene_count += 1
            if direction == 'UP':
                up_genes.append(row)
            else:
                down_genes.append(row)
        else:
            ambiguous_targets.append(row)

        client = CreedsClient(gene)
        single_perturbations = client.get_single_drug_perturbations()
        row_vote_map = _collect_disease_gene_votes(single_perturbations, disease_lookup)
        row['common_disease_gene_count'] = len(row_vote_map)

        if not row_vote_map:
            row['effect'] = 'NO_DISEASE_MATCH'
            no_disease_overlap_genes.append(gene)
            results.append(row)
            continue

        matched_gene_count += 1
        row['disease_direction'] = 'MULTI'
        row_beneficial_votes = float(sum(v['beneficial_votes'] for v in row_vote_map.values()))
        row_harmful_votes = float(sum(v['harmful_votes'] for v in row_vote_map.values()))
        weighted_row_beneficial_votes = row_beneficial_votes * target_weight
        weighted_row_harmful_votes = row_harmful_votes * target_weight
        row['weighted_beneficial_votes'] = _round_metric(weighted_row_beneficial_votes)
        row['weighted_harmful_votes'] = _round_metric(weighted_row_harmful_votes)
        row['disease_score'] = _round_metric(
            sum(float(disease_lookup[disease_gene]['abs_score']) for disease_gene in row_vote_map)
        )

        if weighted_row_beneficial_votes > weighted_row_harmful_votes:
            row['effect'] = 'BENEFICIAL'
            beneficial_gene_count += 1
        elif weighted_row_harmful_votes > weighted_row_beneficial_votes:
            row['effect'] = 'HARMFUL'
            harmful_gene_count += 1
        else:
            row['effect'] = 'MIXED'
            uncertain_gene_count += 1

        for disease_gene, votes in row_vote_map.items():
            disease_gene_vote_map[disease_gene]['beneficial_votes'] += float(votes['beneficial_votes']) * target_weight
            disease_gene_vote_map[disease_gene]['harmful_votes'] += float(votes['harmful_votes']) * target_weight

        results.append(row)

    beneficial_disease_genes = []
    harmful_disease_genes = []
    uncertain_disease_genes = []
    tied_disease_gene_count = 0
    no_vote_disease_gene_count = 0
    uncertain_disease_gene_count = 0

    for disease_gene, votes in disease_gene_vote_map.items():
        disease_abs_score = float(disease_lookup[disease_gene]['abs_score'])
        beneficial_votes = float(votes.get('beneficial_votes', 0.0) or 0.0)
        harmful_votes = float(votes.get('harmful_votes', 0.0) or 0.0)

        if beneficial_votes <= 0 and harmful_votes <= 0:
            no_vote_disease_gene_count += 1
            uncertain_disease_gene_count += 1
            uncertain_sum += disease_abs_score
            uncertain_disease_genes.append({
                'gene': disease_gene,
                'score': _round_metric(disease_abs_score),
                'beneficial_votes': 0.0,
                'harmful_votes': 0.0,
                'reason': 'NO_VOTE',
            })
            continue

        weighted_mass = _weighted_disease_gene_mass(disease_abs_score, beneficial_votes, harmful_votes)
        if beneficial_votes > harmful_votes:
            beneficial_sum += weighted_mass
            beneficial_disease_genes.append({
                'gene': disease_gene,
                'score': _round_metric(weighted_mass),
                'raw_score': _round_metric(disease_abs_score),
                'beneficial_votes': _round_metric(beneficial_votes),
                'harmful_votes': _round_metric(harmful_votes),
            })
        elif harmful_votes > beneficial_votes:
            harmful_sum += weighted_mass
            harmful_disease_genes.append({
                'gene': disease_gene,
                'score': _round_metric(weighted_mass),
                'raw_score': _round_metric(disease_abs_score),
                'beneficial_votes': _round_metric(beneficial_votes),
                'harmful_votes': _round_metric(harmful_votes),
            })
        else:
            tied_disease_gene_count += 1
            uncertain_disease_gene_count += 1
            uncertain_sum += disease_abs_score
            uncertain_disease_genes.append({
                'gene': disease_gene,
                'score': _round_metric(disease_abs_score),
                'beneficial_votes': _round_metric(beneficial_votes),
                'harmful_votes': _round_metric(harmful_votes),
                'reason': 'TIE',
            })

    total_score_mass = beneficial_sum + harmful_sum
    final_score = 0.0 if total_score_mass == 0 else beneficial_sum / total_score_mass
    coverage = 0.0 if len(input_genes) == 0 else matched_gene_count / len(input_genes)
    disease_evidence_coverage = 0.0 if disease_signature_total_abs_score == 0 else total_score_mass / disease_signature_total_abs_score
    uncertain_fraction = 0.0 if disease_signature_total_abs_score == 0 else uncertain_sum / disease_signature_total_abs_score
    vote_balance = 0.0 if total_score_mass == 0 else abs(beneficial_sum - harmful_sum) / total_score_mass
    confidence_balance_component = CONFIDENCE_BALANCE_BASE + (CONFIDENCE_BALANCE_WEIGHT * vote_balance)
    clamped_uncertain_fraction = min(max(uncertain_fraction, 0.0), 1.0)
    certainty_factor = 1.0 - clamped_uncertain_fraction
    confidence = disease_evidence_coverage * confidence_balance_component * certainty_factor

    reason_breakdown = {
        'not_found': len(not_found_genes),
        'ambiguous_or_low_confidence_targets': len(ambiguous_targets),
        'no_disease_overlap': len(no_disease_overlap_genes),
        'harmful_targets': harmful_gene_count,
        'uncertain_disease_genes': uncertain_disease_gene_count,
    }
    dominant_low_score_reason = max(reason_breakdown, key=reason_breakdown.get) if reason_breakdown else None

    return {
        'disease': disease,
        'genes_matched': len(results),
        'results': results,
        'input_genes': input_genes,
        'up_genes': up_genes,
        'down_genes': down_genes,
        'discarded_ambiguous_count': len(ambiguous_targets),
        'not_found_count': len(not_found_genes),
        'discarded_ambiguous': ambiguous_targets,
        'not_found_genes': not_found_genes,
        'classified_gene_count': classified_gene_count,
        'matched_gene_count': matched_gene_count,
        'coverage': _round_metric(coverage),
        'beneficial_gene_count': beneficial_gene_count,
        'harmful_gene_count': harmful_gene_count,
        'uncertain_gene_count': uncertain_gene_count,
        'beneficial_sum': _round_metric(beneficial_sum),
        'harmful_sum': _round_metric(harmful_sum),
        'uncertain_sum': _round_metric(uncertain_sum),
        'disease_gene_count': len(disease_lookup),
        'beneficial_disease_gene_count': len(beneficial_disease_genes),
        'harmful_disease_gene_count': len(harmful_disease_genes),
        'uncertain_disease_gene_count': uncertain_disease_gene_count,
        'tied_disease_gene_count': tied_disease_gene_count,
        'no_vote_disease_gene_count': no_vote_disease_gene_count,
        'final_score': _round_metric(final_score),
        'interpretation': _interpret_final_score(final_score),
        'confidence': _round_metric(confidence),
        'disease_evidence_coverage': _round_metric(disease_evidence_coverage),
        'uncertain_fraction': _round_metric(uncertain_fraction),
        'beneficial_disease_genes': sorted(beneficial_disease_genes, key=lambda x: x['gene']),
        'harmful_disease_genes': sorted(harmful_disease_genes, key=lambda x: x['gene']),
        'uncertain_disease_genes': sorted(uncertain_disease_genes, key=lambda x: x['gene']),
        'beneficial_disease_score_total': _round_metric(beneficial_sum),
        'disease_signature_total_score': _round_metric(disease_signature_total_abs_score),
        'low_score_reason_breakdown': reason_breakdown,
        'dominant_low_score_reason': dominant_low_score_reason,
    }


def run_calibration_benchmark() -> dict:
    calibration = _load_scoring_calibration()
    cases = calibration.get('benchmark_cases', [])
    thresholds = calibration.get('interpretation_thresholds', {})

    if not isinstance(cases, list) or len(cases) == 0:
        return {
            'total_cases': 0,
            'evaluated_cases': 0,
            'passed_cases': 0,
            'pass_rate': 0.0,
            'cases': [],
            'thresholds': thresholds,
            'message': 'No benchmark cases configured.',
        }

    evaluations = []
    passed = 0
    evaluated = 0

    for case in cases:
        case_name = str(case.get('name', 'unnamed_case'))
        disease = str(case.get('disease', '')).strip()
        genes = [str(g).strip() for g in (case.get('genes') or []) if str(g).strip()]
        expected = str(case.get('expected', '')).strip().lower()

        if not disease or not genes or expected not in {'positive', 'negative'}:
            evaluations.append({
                'name': case_name,
                'status': 'SKIPPED',
                'reason': 'INVALID_CASE_CONFIGURATION',
                'expected': expected,
                'disease': disease,
                'genes': genes,
            })
            continue

        try:
            result = match_gene_set(genes, disease)
            score = float(result.get('final_score', 0.0) or 0.0)
            min_expected_score = float(case.get('min_expected_score', thresholds.get('mixed_effect_min', 0.40)))
            max_expected_score = float(case.get('max_expected_score', thresholds.get('mixed_effect_min', 0.40)))
            if expected == 'positive':
                case_passed = score >= min_expected_score
            else:
                case_passed = score <= max_expected_score

            evaluated += 1
            if case_passed:
                passed += 1

            evaluations.append({
                'name': case_name,
                'status': 'PASS' if case_passed else 'FAIL',
                'expected': expected,
                'disease': disease,
                'score': _round_metric(score),
                'confidence': _round_metric(float(result.get('confidence', 0.0) or 0.0)),
                'coverage': _round_metric(float(result.get('coverage', 0.0) or 0.0)),
                'uncertain_fraction': _round_metric(float(result.get('uncertain_fraction', 0.0) or 0.0)),
                'min_expected_score': _round_metric(min_expected_score),
                'max_expected_score': _round_metric(max_expected_score),
            })
        except Exception:
            evaluations.append({
                'name': case_name,
                'status': 'ERROR',
                'expected': expected,
                'disease': disease,
                'error': 'BENCHMARK_EVALUATION_FAILED',
            })

    pass_rate = 0.0 if evaluated == 0 else passed / evaluated
    return {
        'total_cases': len(cases),
        'evaluated_cases': evaluated,
        'passed_cases': passed,
        'pass_rate': _round_metric(pass_rate),
        'thresholds': thresholds,
        'cases': evaluations,
    }




if __name__ == "__main__":
    gene = "HRH1"
    disease = "pulmonary hypertension"
    obj = CreedsClient(gene)
    disease_signatures = get_disease_signatures(disease)
    single_drug_perturbations = obj.get_single_drug_perturbations()
    print(disease_signatures)
    print(single_drug_perturbations)
    print(type(obj.match_genes(disease_signatures, single_drug_perturbations)))
