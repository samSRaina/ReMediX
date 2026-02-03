import requests, logging
from functools import lru_cache
import json

logging.basicConfig(level=logging.INFO)
logger= logging.getLogger(__name__)

@lru_cache(maxsize=128)
def get_smile(name: str) -> str | None:
    url= f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/SMILES/JSON"

    try:
        r= requests.get(url, timeout= 10)
        r.raise_for_status()

        data= r.json()
        return data["PropertyTable"]["Properties"][0].get("SMILES")
    except requests.RequestException as e:
        if e.response:
            logger.error(f"{e.response.status_code}")
        else:
            logger.error(f"{e}")
        return None


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
def get_properties(name: str):
    props_string=",".join(properties)
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