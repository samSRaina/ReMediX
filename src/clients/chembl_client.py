from chembl_webresource_client.new_client import new_client

class ChEMBLClient:
    def __init__(self):
        self.molecule = new_client.molecule
        self.activity = new_client.activity

    def get_by_inchikey(self, inchi_key: str) -> list:
        compound = list(self.molecule.filter(molecule_structures__standard_inchi_key = inchi_key))
        chembl_id = compound[0].get('molecule_chembl_id')
        activities = list(self.activity.filter(molecule_chembl_id = chembl_id))
        ic50_activities = [act for act in activities if act.get('standard_type') == 'IC50']

        act_data = []
        for act in ic50_activities:
            act_data.append({
                'target_chembl_id': act.get('target_chembl_id'),
                'target_name': act.get('target_pref_name'),
                'target_organism': act.get('target_organism'),
                'standard_type': act.get('standard_type'),
                'standard_units': act.get('standard_units'),
                'standard_value': act.get('standard_value')
            })

        #return json.dumps(act_data, indent=2)
        return act_data

if __name__ == "__main__":
    inchi_key = "ZKLPARSLTMPFCP-UHFFFAOYSA-N"
    obj = ChEMBLClient()
    print(obj.get_by_inchikey(inchi_key))