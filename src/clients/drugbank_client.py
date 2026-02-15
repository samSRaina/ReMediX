from pathlib import Path
from lxml import etree
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DrugBankClient:
    NS = {'db': 'http://www.drugbank.ca'}
    DEFAULT_XML_PATH = Path(__file__).resolve().parent.parent / 'data' / 'drugBank' / 'full database.xml'

    def __init__(self, xml_path: Path = None):
        self.xml_path = xml_path or self.DEFAULT_XML_PATH

    def search_drug_by_inchikey(self, inchikey: str) -> Optional[dict]:
        for event, elem in etree.iterparse(str(self.xml_path),
                                           events=('end',),
                                           tag='{http://www.drugbank.ca}drug'):
            calc_props = elem.find('db:calculated-properties', self.NS)
            if calc_props is not None:
                for prop in calc_props.findall('db:property', self.NS):
                    kind = prop.find('db:kind', self.NS)
                    if kind is not None and kind.text == 'InChIKey':
                        value = prop.find('db:value', self.NS)
                        if value is not None and value.text == inchikey:
                            drug_data = self._extract_drug_data(elem)
                            elem.clear()
                            return drug_data
            elem.clear()
        return None

    def _extract_drug_data(self, drug_elem) -> dict:
        """Extract relevant data from a drug XML element."""
        data = {}

        drugbank_id = drug_elem.find('db:drugbank-id[@primary="true"]', self.NS)
        if drugbank_id is None:
            drugbank_id = drug_elem.find('db:drugbank-id', self.NS)
        data['drugbank_id'] = drugbank_id.text if drugbank_id is not None else None

        name = drug_elem.find('db:name', self.NS)
        data['name'] = name.text if name is not None else None

        groups = drug_elem.findall('db:groups/db:group', self.NS)
        data['groups'] = [g.text for g in groups]

        indication = drug_elem.find('db:indication', self.NS)
        data['indication'] = indication.text if indication is not None else None

        categories = drug_elem.findall('db:categories/db:category/db:category', self.NS)
        data['categories'] = [c.text for c in categories]

        targets = drug_elem.findall('db:targets/db:target/db:target', self.NS)
        data['targets'] = [t.text for t in targets]

        calc_props = drug_elem.find('db:calculated-properties', self.NS)
        if calc_props is not None:
            for prop in calc_props.findall('db:property', self.NS):
                kind = prop.find('db:kind', self.NS)
                value = prop.find('db:value', self.NS)
                if kind is not None and value is not None:
                    prop_name = kind.text.lower().replace(' ', '_').replace('-', '_')
                    data[prop_name] = value.text

        return data


if __name__ == "__main__":
    client = DrugBankClient()
    result = client.search_drug_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    print(result)

