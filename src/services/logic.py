import requests, logging
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger= logging.getLogger(__name__)

@lru_cache(maxsize=128)
def get_smile(name: str) -> str | None:
    url= f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/SMILES/JSON"

    try:
        r= requests.get(url, timeout= 10)
        r.raise_for_status()

        data= r.json()
        return f"{name}: {data["PropertyTable"]["Properties"][0].get("SMILES")}"
    except requests.RequestException as e:
        logger.error(f"{e.response.status_code}")
        return f"{e.response.status_code}"
