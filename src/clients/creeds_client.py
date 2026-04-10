from pathlib import Path
import json
from functools import lru_cache

DISEASE_SIG = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signatures-v1.0.json'
SINGLE_DRUG_PERTURBATION = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'single_drug_perturbations-v1.0.json'
DISEASE_SIGNATURE_TABLE = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signature_table.json'


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
        beneficial = 0
        harmful = 0
        
        # Create a lookup for disease genes for faster matching
        # Key: gene (lowercase), Value: score
        disease_map = {str(g[0]).strip().lower(): g[1] for g in disease_genes}

        for drug_gene_entry in drug_perturbations:
            gene_sym = str(drug_gene_entry[0]).strip().lower()
            drug_score = drug_gene_entry[1]
            
            if gene_sym in disease_map:
                disease_score = disease_map[gene_sym]
                
                # Opposite signs -> Beneficial (drug reverses disease signature)
                if (drug_score < 0 < disease_score) or (drug_score > 0 > disease_score):
                    beneficial += 1
                # Same signs -> Harmful (drug exacerbates disease signature)
                elif (drug_score < 0 and disease_score < 0) or (drug_score > 0 and disease_score > 0):
                    harmful += 1

        return f"beneficial: {beneficial}", f"harmful: {harmful}"


def match_gene_set(gene_list: list[str], disease: str) -> dict:
    """
    For each gene in the list, match disease signatures against
    single gene perturbations and return beneficial/harmful counts.
    Disease must be provided by the user.
    """
    disease_signatures = get_disease_signatures(disease)
    results = []
    for gene in gene_list:
        client = CreedsClient(gene)
        single_perturbations = client.get_single_drug_perturbations()
        beneficial_str, harmful_str = client.match_genes(disease_signatures, single_perturbations)
        results.append({
            "gene": gene,
            "beneficial": beneficial_str,
            "harmful": harmful_str,
        })
    return {"disease": disease, "genes_matched": len(results), "results": results}




if __name__ == "__main__":
    gene = "HRH1"
    disease = "pulmonary hypertension"
    obj = CreedsClient(gene)
    disease_signatures = get_disease_signatures(disease)
    single_drug_perturbations = obj.get_single_drug_perturbations()
    print(disease_signatures)
    print(single_drug_perturbations)
    print(type(obj.match_genes(disease_signatures, single_drug_perturbations)))
