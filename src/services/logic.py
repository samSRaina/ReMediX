import requests, logging
from src.services.drugbank_parser import get_drug_by_inchikey


logging.basicConfig(level=logging.INFO)
logger= logging.getLogger(__name__)

properties = [
    "SMILES",
    "IUPACName",
    "MolecularFormula",
    "MolecularWeight",
    "InChIKey",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
]
props_string=",".join(properties)


#input via compound name
def get_pubchem_properties(name: str):
    url=f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/{props_string}/JSON"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()

        data=r.json()
        return data["PropertyTable"]["Properties"][0]
    except requests.RequestException as e:
        if e.response:
            logger.error(f"{e.response.status_code}")
        else:
            logger.error(f"{e}")
        return None

#input via smile
def get_pubchem_properties_via_smile(smile: str):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{smile}/property/{props_string}/JSON"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()

        data=r.json()
        return data["PropertyTable"]["Properties"][0]
    except requests.RequestException as e:
        if e.response:
            logger.error(f"{e.response.status_code}")
        else:
            logger.error(f"{e}")
        return None

# DrugBank InChIKey lookup
def get_drugbank_properties_via_inchikey(key: str):
    return get_drug_by_inchikey(key)

