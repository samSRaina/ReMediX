from pathlib import Path
import json
from functools import lru_cache

DISEASE_SIG = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signatures-v1.0.json'
SINGLE_GENE_PERTURBATION = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'single_gene_perturbations-v1.0.json'
DISEASE_SIGNATURE_TABLE = Path(__file__).parent.parent / 'data' / 'CREEDS' / 'disease_signature_table.json'


@lru_cache(maxsize=1)
def _load_disease_signature_dataset() -> list:
    with open(DISEASE_SIG, 'r') as file:
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

    def get_single_gene_perturbations(self) -> list:
        with open(SINGLE_GENE_PERTURBATION, 'r') as file:
            single_gene_perturbations = json.load(file)

        response_dataset = []
        for entry in single_gene_perturbations:
            for subentry in entry.get("up_genes"):
                if subentry[0] == self.uniprot_gene:
                    response_dataset.append(subentry)

            for subentry in entry.get('down_genes'):
                if subentry[0] == self.uniprot_gene:
                    response_dataset.append(subentry)

        return response_dataset

    def match_genes(self, all_genes: list, single_perturbations):
        beneficial = 0
        harmful = 0
        for entry in all_genes:
            if entry[0] == self.uniprot_gene:
                score=entry[1]
                for sgp in single_perturbations:
                    if (sgp[1]<0 and score<0) or (sgp[1]>0 and score) > 0:
                        harmful +=1
                    else: beneficial +=1

        return f"beneficial: {beneficial}",f"harmful: {harmful}"


def match_gene_set(gene_list: list[str]) -> dict:
    """
    For each gene in the list, match disease signatures against
    single gene perturbations and return beneficial/harmful counts.
    Disease is fixed to 'pulmonary hypertension'.
    """
    disease = "pulmonary hypertension"
    disease_signatures = get_disease_signatures(disease)
    results = []
    for gene in gene_list:
        client = CreedsClient(gene)
        single_perturbations = client.get_single_gene_perturbations()
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
    single_gene_perturbations = obj.get_single_gene_perturbations()
    print(disease_signatures)
    print(single_gene_perturbations)
    print(type(obj.match_genes(disease_signatures, single_gene_perturbations)))
