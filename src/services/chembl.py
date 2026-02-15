from chembl_webresource_client.new_client import new_client
from ..services.logic import
molecule = new_client.molecule
mol = molecule.filter(molecule_structures__standard_inchi_key='BSYNRYMUTXBXSQ-UHFFFAOYSA-N').only(['molecule_chembl_id', 'pref_name', 'molecule_structures'])
print(mol)