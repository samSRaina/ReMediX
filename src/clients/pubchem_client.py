import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PubChemClient:
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
    DEFAULT_PROPERTIES = [
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

    def __init__(self):
        self.props_string = ",".join(self.DEFAULT_PROPERTIES)

    def _fetch(self, url: str) -> dict | None:
        """Reusable method to fetch data from PubChem API."""
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.json()["PropertyTable"]["Properties"][0]
        except requests.RequestException as e:
            status = getattr(e.response, 'status_code', None)
            logger.error(f"PubChem API error: {status or e}")
            return None

    def search_by_name(self, name: str) -> dict | None:
        url = f"{self.BASE_URL}/name/{name}/property/{self.props_string}/JSON"
        return self._fetch(url)

    def search_by_smile(self, smile: str) -> dict | None:
        url = f"{self.BASE_URL}/smiles/{smile}/property/{self.props_string}/JSON"
        return self._fetch(url)

    def get_inchikey(self, name: str) -> str | None:
        """Get only the InChIKey for a compound by name."""
        url = f"{self.BASE_URL}/name/{name}/property/InChIKey/JSON"
        result = self._fetch(url)
        return result.get("InChIKey") if result else None

if __name__ == "__main__":
    name = "cetirizine"
    obj = PubChemClient()
    print(obj.get_inchikey(name))