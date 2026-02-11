from pathlib import Path
from lxml import etree
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ns = {'db': 'http://www.drugbank.ca'}
xml_path = Path(__file__).resolve().parent.parent / 'db' / 'drugbank_all_full_database.xml' / 'full database.xml'


def get_drug_by_inchikey(inchikey: str) -> Optional[dict]:
    for event, elem in etree.iterparse(str(xml_path),
                                       events=('end',),
                                       tag='{http://www.drugbank.ca}drug'):
        calc_props = elem.find('db:calculated-properties', ns)
        if calc_props is not None:
            for prop in calc_props.findall('db:property', ns):
                kind = prop.find('db:kind', ns)
                if kind is not None and kind.text == 'InChIKey':
                    value = prop.find('db:value', ns)
                    if value is not None and value.text == inchikey:
                        # Found the drug - extract relevant data
                        drug_data = extract_drug_data(elem)
                        elem.clear()
                        return drug_data
        elem.clear()
    return None


def extract_drug_data(drug_elem):
    data = {}

    drugbank_id = drug_elem.find('db:drugbank-id[@primary="true"]', ns)
    if drugbank_id is None:
        drugbank_id = drug_elem.find('db:drugbank-id', ns)
    data['drugbank_id'] = drugbank_id.text if drugbank_id is not None else None

    name = drug_elem.find('db:name', ns)
    data['name'] = name.text if name is not None else None

    groups = drug_elem.findall('db:groups/db:group', ns)
    data['groups'] = [g.text for g in groups]

    indication = drug_elem.find('db:indication', ns)
    data['indication'] = indication.text if indication is not None else None

    categories = drug_elem.findall('db:categories/db:category/db:category', ns)
    data['categories'] = [c.text for c in categories]

    targets = drug_elem.findall('db:targets/db:target/db:target', ns)
    data['targets'] = [t.text for t in targets]

    # Calculated properties (SMILES, InChI, InChIKey, etc.)
    calc_props = drug_elem.find('db:calculated-properties', ns)
    if calc_props is not None:
        for prop in calc_props.findall('db:property', ns):
            kind = prop.find('db:kind', ns)
            value = prop.find('db:value', ns)
            if kind is not None and value is not None:
                # Convert property names to snake_case
                prop_name = kind.text.lower().replace(' ', '_').replace('-', '_')
                data[prop_name] = value.text

    return data
