from pathlib import Path
import json

DISEASE_SIG = Path(__file__).parent.parent/'data'/'CREEDS'/'disease_signatures-v1.0.json'
SINGLE_GENE_PERTURBATION = Path(__file__).parent.parent/'data'/'CREEDS'/'single_gene_perturbations-v1.0.json'


def get_disease_signatures(disease) -> list:
    with open(DISEASE_SIG, 'r') as file:
        disease_signatures = json.load(file)

    response_dataset = [entry for entry in disease_signatures if entry.get('disease_name') == disease]
    return response_dataset[0].get('up_genes') + response_dataset[0].get('down_genes', [])


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
