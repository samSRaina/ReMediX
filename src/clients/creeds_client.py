from pathlib import Path
import json
from functools import lru_cache


DISEASE_SIG = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signatures-v1.0.json'
SINGLE_DRUG_PERTURBATION = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'single_drug_perturbations-v1.0.json'
DISEASE_SIGNATURE_TABLE = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signature_table.json'
RATIO_THRESHOLD = 1.2


@lru_cache(maxsize=1)
def _load_disease_signature_dataset() -> list:
    with open(DISEASE_SIG, 'r') as file:
        return json.load(file)


@lru_cache(maxsize=1)
def _load_drug_perturbation_dataset() -> list:
    with open(SINGLE_DRUG_PERTURBATION, 'r') as file:
        return json.load(file)


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
    if denominator == 0:
        return float('inf')
    return float(numerator) / float(denominator)


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    Two-stage behavior:
    1) Classify each input gene by ratio from aggregated single-gene perturbation counts.
       - ratio = max(up, down) / min(up, down)
       - ratio <= 1.2 => AMBIGUOUS
       - ratio > 1.2  => UP or DOWN by dominant side
    2) For non-ambiguous genes only, run original disease-signature matching to
       compute beneficial/harmful and beneficial disease genes.

    For each input gene, classify direction from aggregated single-gene
    perturbation counts:
    - ratio = max(up, down) / min(up, down)
    - ratio <= 1.2 => ambiguous (discard)
    - ratio > 1.2  => dominant direction (UP or DOWN)
    """
    perturbation_index = _load_single_gene_perturbation_index()

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

    disease_signatures = get_disease_signatures(disease) if disease else []
    disease_map: dict[str, float] = {}
    disease_total_score = 0.0
    for row in disease_signatures:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        gene = str(row[0]).strip().lower()
        score = _to_float(row[1])
        if score is not None:
            disease_total_score += score
        if gene and score is not None:
            disease_map[gene] = score

    results = []
    up_genes = []
    down_genes = []
    discarded_ambiguous = []
    not_found_genes = []
    beneficial_disease_gene_map: dict[str, float] = {}

    for gene in input_genes:
        key = gene.upper()
        counts = perturbation_index.get(key)
        if not counts:
            not_found_genes.append(gene)
            continue

        up_count = int(counts.get('up_count', 0) or 0)
        down_count = int(counts.get('down_count', 0) or 0)
        ratio = _compute_ratio(up_count, down_count)

        row = {
            'gene': gene,
            'up_count': up_count,
            'down_count': down_count,
            'ratio': ratio,
            'classification': 'AMBIGUOUS',
            'direction': 'AMBIGUOUS',
            'beneficial_count': 0,
            'harmful_count': 0,
            'beneficial': 'beneficial: 0',
            'harmful': 'harmful: 0',
            'beneficial_disease_genes': [],
            'beneficial_disease_gene_score': 0.0,
        }

        if ratio <= RATIO_THRESHOLD:
            discarded_ambiguous.append(row)
            results.append(row)
            continue

        if up_count > down_count:
            row['classification'] = 'UP'
            row['direction'] = 'UP'
            up_genes.append(row)
        elif down_count > up_count:
            row['classification'] = 'DOWN'
            row['direction'] = 'DOWN'
            down_genes.append(row)
        else:
            discarded_ambiguous.append(row)
            results.append(row)
            continue

        client = CreedsClient(gene)
        single_perturbations = client.get_single_drug_perturbations()
        beneficial_count, harmful_count, beneficial_disease_genes = _match_perturbations_against_disease(
            single_perturbations,
            disease_map,
        )

        row['beneficial_count'] = beneficial_count
        row['harmful_count'] = harmful_count
        row['beneficial'] = f'beneficial: {beneficial_count}'
        row['harmful'] = f'harmful: {harmful_count}'
        row['beneficial_disease_genes'] = sorted(beneficial_disease_genes)

        beneficial_gene_score = 0.0
        for disease_gene in beneficial_disease_genes:
            disease_gene_lower = disease_gene.lower()
            gene_score = disease_map.get(disease_gene_lower)
            if gene_score is None:
                continue
            beneficial_disease_gene_map[disease_gene] = gene_score
            beneficial_gene_score += gene_score

        row['beneficial_disease_gene_score'] = beneficial_gene_score
        results.append(row)

    beneficial_disease_genes = [
        {
            'gene': gene,
            'score': score,
        }
        for gene, score in sorted(beneficial_disease_gene_map.items())
    ]

    beneficial_disease_score_total = sum(item['score'] for item in beneficial_disease_genes)

    return {
        'disease': disease,
        'genes_matched': len(results),
        'results': results,
        'input_genes': input_genes,
        'up_genes': up_genes,
        'down_genes': down_genes,
        'discarded_ambiguous_count': len(discarded_ambiguous),
        'not_found_count': len(not_found_genes),
        'discarded_ambiguous': discarded_ambiguous,
        'not_found_genes': not_found_genes,
        'beneficial_disease_genes': beneficial_disease_genes,
        'beneficial_disease_score_total': beneficial_disease_score_total,
        'disease_signature_total_score': disease_total_score,
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
