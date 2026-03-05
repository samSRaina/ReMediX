import logging

logger = logging.getLogger(__name__)

# Lazy import - ChEMBL client will be loaded on first use
_new_client = None

def _get_chembl_client():
    """Lazy load ChEMBL client to avoid import-time failures when API is down."""
    global _new_client
    if _new_client is None:
        try:
            from chembl_webresource_client.new_client import new_client
            _new_client = new_client
        except Exception as e:
            logger.error(f"Failed to connect to ChEMBL API: {e}")
            raise ConnectionError(f"ChEMBL API is currently unavailable: {e}")
    return _new_client

class ChEMBLClient:
    def __init__(self):
        self._molecule = None
        self._activity = None
        self._target = None
        # Cache to store target data (avoids repeated API calls)
        self._target_cache = {}

    @property
    def molecule(self):
        if self._molecule is None:
            self._molecule = _get_chembl_client().molecule
        return self._molecule

    @property
    def activity(self):
        if self._activity is None:
            self._activity = _get_chembl_client().activity
        return self._activity

    @property
    def target(self):
        if self._target is None:
            self._target = _get_chembl_client().target
        return self._target

    def _get_target_cached(self, target_chembl_id: str) -> dict:
        """
        Fetch target data with caching to avoid repeated API calls.
        """
        if target_chembl_id not in self._target_cache:
            self._target_cache[target_chembl_id] = self.target.get(target_chembl_id) or {}
        return self._target_cache[target_chembl_id]

    def _batch_fetch_targets(self, target_ids: list) -> None:
        """
        Batch fetch multiple targets at once and store in cache.
        Much faster than fetching one-by-one.
        """
        # Filter out already cached targets
        uncached_ids = [tid for tid in target_ids if tid and tid not in self._target_cache]

        if not uncached_ids:
            return  # All already cached

        # Batch fetch all uncached targets in ONE API call
        targets = list(self.target.filter(target_chembl_id__in=uncached_ids))

        # Store in cache
        for t in targets:
            self._target_cache[t.get('target_chembl_id')] = t

        # Mark missing targets as empty dict to avoid re-fetching
        for tid in uncached_ids:
            if tid not in self._target_cache:
                self._target_cache[tid] = {}

    def _extract_protein_classification(self, target_data: dict) -> str:
        """Return the exact protein_classification value from ChEMBL. '--' if missing."""
        value = target_data.get('protein_classification')
        return value if value else '--'

    def _extract_gene_symbol(self, target_data: dict) -> str:
        """Extract the gene symbol from target_components."""
        for comp in target_data.get('target_components', []):
            # Try target_component_synonyms with syn_type == GENE_SYMBOL
            for syn in comp.get('target_component_synonyms', []):
                if syn.get('syn_type') == 'GENE_SYMBOL':
                    value = syn.get('component_synonym')
                    return value if value else '--'
        return '--'

    def _extract_uniprot_id(self, target_data: dict) -> str:
        """Extract the primary UniProt accession from target_components."""
        for comp in target_data.get('target_components', []):
            accession = comp.get('accession')
            if accession:
                return accession
        return '--'

    def get_by_inchikey(self, inchi_key: str, standard_type: str = None, include_target_details: bool = False, only_with_target_type: bool = False) -> list:
        compound = list(self.molecule.filter(molecule_structures__standard_inchi_key=inchi_key))
        if not compound:
            return []

        chembl_id = compound[0].get('molecule_chembl_id')
        activities = list(self.activity.filter(molecule_chembl_id=chembl_id))

        # Filter by standard_type if provided
        if standard_type:
            activities = [act for act in activities if act.get('standard_type') == standard_type]

        # Always batch-fetch targets so we can enrich with gene symbol, uniprot, classification
        unique_target_ids = list(set(
            act.get('target_chembl_id') for act in activities if act.get('target_chembl_id')
        ))
        self._batch_fetch_targets(unique_target_ids)

        act_data = []
        for act in activities:
            target_chembl_id = act.get('target_chembl_id')

            # Enrich from cached target data
            target_info = self._get_target_cached(target_chembl_id) if target_chembl_id else {}
            target_type = target_info.get('target_type') or None

            # Skip activities without target_type if flag is set
            if only_with_target_type and not target_type:
                continue

            # Extract enriched fields
            gene_symbol = self._extract_gene_symbol(target_info) if target_info else '--'
            uniprot_id = self._extract_uniprot_id(target_info) if target_info else '--'
            protein_classification = self._extract_protein_classification(target_info) if target_info else '--'

            activity_entry = {
                'target_chembl_id': target_chembl_id or '--',
                'target_name': act.get('target_pref_name') or '--',
                'target_type': target_type or '--',
                'target_organism': act.get('target_organism') or '--',
                'gene_symbol': gene_symbol,
                'uniprot_id': uniprot_id,
                'standard_type': act.get('standard_type') or '--',
                'standard_value': act.get('standard_value') or '--',
                'standard_units': act.get('standard_units') or '--',
                'protein_target_classification': protein_classification,
            }

            # Optionally include enriched target details
            if include_target_details and target_chembl_id:
                activity_entry['target_details'] = self.get_target_data(target_chembl_id)

            act_data.append(activity_entry)

        return act_data

    def get_target_data(self, target_chembl_id: str) -> dict:
        """
        Fetch detailed target information using target_chembl_id
        """
        target_data = self.target.get(target_chembl_id)
        if not target_data:
            return {}

        # Extract UniProt accessions from target components
        accessions = [
            comp.get('accession')
            for comp in target_data.get('target_components', [])
            if comp.get('accession')
        ]

        return {
            'protein_name': target_data.get('pref_name'),
            'protein_classification': target_data.get('target_type'),
            'uniprot_accession': accessions[0] if len(accessions) == 1 else accessions if accessions else None
        }

if __name__ == "__main__":
    inchi_key = "ZKLPARSLTMPFCP-UHFFFAOYSA-N"
    obj = ChEMBLClient()
    print(obj.get_by_inchikey(inchi_key, "IC50"))
