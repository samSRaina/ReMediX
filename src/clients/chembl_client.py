from chembl_webresource_client.new_client import new_client

class ChEMBLClient:
    def __init__(self):
        self.molecule = new_client.molecule
        self.activity = new_client.activity

    def get_by_inchikey(self, inchi_key: str, standard_type: str = None) -> list:
        compound = list(self.molecule.filter(molecule_structures__standard_inchi_key=inchi_key))
        if not compound:
            return []

        chembl_id = compound[0].get('molecule_chembl_id')
        activities = list(self.activity.filter(molecule_chembl_id=chembl_id))

        # Filter by standard_type if provided
        if standard_type:
            activities = [act for act in activities if act.get('standard_type') == standard_type]

        act_data = []
        for act in activities:
            act_data.append({
                'target_chembl_id': act.get('target_chembl_id'),
                'target_name': act.get('target_pref_name'),
                'target_type': act.get('target_type'),
                'target_organism': act.get('target_organism'),
                'standard_type': act.get('standard_type'),
                'standard_value': act.get('standard_value'),
                'standard_units': act.get('standard_units')
            })

        return act_data

if __name__ == "__main__":
    inchi_key = "ZKLPARSLTMPFCP-UHFFFAOYSA-N"
    obj = ChEMBLClient()
    print(obj.get_by_inchikey(inchi_key, "IC50"))
