import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Lazy import - ChEMBL client will be loaded on first use
_new_client = None
_client_lock = threading.Lock()

# Shared, process-wide executor for batch target fetching. Created once and
# reused across requests instead of per-call pools.
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()

# Upper bound on activities fetched per molecule. Well-studied compounds have
# thousands of rows; beyond this the payload is huge and latency dominates.
# Fetches are slice-bounded (QuerySet[:cap]) — the SDK's pagination stops at
# the slice stop, so this caps BOTH the result size and the number of HTTP
# round trips (at page size 100, 2000 records = 20 requests, not 100).
MAX_ACTIVITIES_PER_MOLECULE = 2000

# Raise the ChEMBL SDK page size from its default 20 to 100 (the API's max).
# Must happen BEFORE the first `new_client` import/construction because the
# QuerySet reads Settings.MAX_LIMIT at query time. This reduces HTTP calls
# 5x with zero behavior change.
def _raise_sdk_page_size() -> None:
    from chembl_webresource_client.settings import Settings

    settings = Settings.Instance()
    if settings.MAX_LIMIT < 100:
        settings.MAX_LIMIT = 100

# Cache size bounds (entries) to prevent unbounded memory growth.
MAX_TARGET_CACHE_ENTRIES = 20_000
MAX_ACTIVITIES_CACHE_ENTRIES = 500


def _get_chembl_client():
    """Lazy load ChEMBL client to avoid import-time failures when API is down."""
    global _new_client
    if _new_client is None:
        with _client_lock:
            if _new_client is None:  # re-check under lock
                try:
                    _raise_sdk_page_size()
                    from chembl_webresource_client.new_client import new_client
                    _new_client = new_client
                except Exception as e:
                    logger.error(f"Failed to connect to ChEMBL API: {e}")
                    raise ConnectionError(f"ChEMBL API is currently unavailable: {e}")
    return _new_client


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:  # re-check under lock
                _executor = ThreadPoolExecutor(
                    max_workers=8, thread_name_prefix="chembl-fetch"
                )
    return _executor


class _BoundedCache:
    """Minimal thread-safe dict cache with an insertion-order size bound.

    Simple eviction: when full, drop the oldest entry (FIFO). Good enough for
    reference-data caches; avoids unbounded memory growth in long-running
    processes.
    """

    def __init__(self, max_entries: int):
        self._max_entries = max_entries
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def put(self, key, value) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self._max_entries:
                # Evict oldest inserted key.
                oldest = next(iter(self._data))
                del self._data[oldest]
            self._data[key] = value

    def contains(self, key) -> bool:
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


class ChEMBLClient:
    # Class-level caches shared across instances, now thread-safe and bounded.
    _target_cache = _BoundedCache(MAX_TARGET_CACHE_ENTRIES)
    _activities_cache = _BoundedCache(MAX_ACTIVITIES_CACHE_ENTRIES)

    def __init__(self):
        self._molecule = None
        self._activity = None
        self._target = None

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
        """Fetch target data with caching to avoid repeated API calls."""
        cached = self._target_cache.get(target_chembl_id)
        if cached is None:
            cached = self.target.get(target_chembl_id) or {}
            self._target_cache.put(target_chembl_id, cached)
        return cached

    def _batch_fetch_targets(self, target_ids: list) -> None:
        """Batch fetch multiple targets at once and store in cache."""
        uncached_ids = [tid for tid in target_ids if tid and not self._target_cache.contains(tid)]

        if not uncached_ids:
            return  # All already cached

        # Batch fetch all uncached targets in ONE API call
        try:
            targets = list(self.target.filter(target_chembl_id__in=uncached_ids)[:len(uncached_ids)])
        except Exception as e:
            # A failed batch should not poison already-cached results, but we
            # must not cache empties either (the API may be transiently down).
            logger.warning(f"Batch target fetch failed for {len(uncached_ids)} ids: {e}")
            return

        for t in targets:
            self._target_cache.put(t.get('target_chembl_id'), t)

        # Mark missing targets as empty dict to avoid re-fetching
        for tid in uncached_ids:
            if not self._target_cache.contains(tid):
                self._target_cache.put(tid, {})

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

    def _fetch_all_activities(self, inchi_key: str) -> list:
        """
        Fetch the molecule + its activities (bounded).
        Results are cached on the class so repeated calls are free.
        """
        cached = self._activities_cache.get(inchi_key)
        if cached is not None:
            return cached

        try:
            compound = list(self.molecule.filter(molecule_structures__standard_inchi_key=inchi_key))
        except Exception as e:
            logger.error(f"Error fetching molecule for {inchi_key}: {e}")
            # Do not cache failures; allow a later retry.
            return []

        if not compound:
            self._activities_cache.put(inchi_key, [])
            return []

        chembl_id = compound[0].get('molecule_chembl_id')

        try:
            # Slice-bounded fetch: the SDK's pagination stops at the slice
            # stop, capping both payload size and HTTP round trips.
            activities = list(
                self.activity.filter(molecule_chembl_id=chembl_id)[:MAX_ACTIVITIES_PER_MOLECULE]
            )
        except Exception as e:
            logger.error(f"Error fetching activities for {chembl_id}: {e}")
            return []

        # Batch-fetch ALL targets referenced by these activities in chunks.
        unique_target_ids = list(set(
            act.get('target_chembl_id') for act in activities if act.get('target_chembl_id')
        ))

        # Split into chunks of 50 to avoid URL length issues or timeouts.
        chunk_size = 50
        chunks = [unique_target_ids[i:i + chunk_size] for i in range(0, len(unique_target_ids), chunk_size)]

        # Fetch chunks in PARALLEL on the shared executor; consume results so
        # exceptions surface instead of being swallowed by executor.map.
        if chunks:
            futures = [_get_executor().submit(self._batch_fetch_targets, chunk) for chunk in chunks]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.warning(f"Target chunk fetch failed: {e}")

        self._activities_cache.put(inchi_key, activities)
        return activities

    def _enrich_activity(self, act: dict, include_target_details: bool = False) -> dict:
        """Build an enriched activity dict from a raw ChEMBL activity record."""
        target_chembl_id = act.get('target_chembl_id')
        target_info = self._get_target_cached(target_chembl_id) if target_chembl_id else {}
        target_type = target_info.get('target_type') or None

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
            'standard_relation': act.get('standard_relation') or '--',
            'assay_chembl_id': act.get('assay_chembl_id') or '--',
            'assay_type': act.get('assay_type') or '--',
            'assay_description': act.get('assay_description') or '--',
            'protein_target_classification': protein_classification,
        }

        if include_target_details and target_chembl_id:
            activity_entry['target_details'] = self.get_target_data(target_chembl_id)

        return activity_entry

    def get_by_inchikey(self, inchi_key: str, standard_type: str = None, include_target_details: bool = False, only_with_target_type: bool = False) -> list:
        activities = self._fetch_all_activities(inchi_key)
        if not activities:
            return []

        # Filter by standard_type if provided
        if standard_type:
            activities = [act for act in activities if act.get('standard_type') == standard_type]

        act_data = []
        for act in activities:
            entry = self._enrich_activity(act, include_target_details)
            if only_with_target_type and entry['target_type'] == '--':
                continue
            act_data.append(entry)

        return act_data

    def get_gene_set(self, inchi_key: str) -> set:
        """
        Collect all valid gene symbols for IC50, AC50, and Ki.
        Uses the same cached activities — no extra API calls.
        """
        activities = self._fetch_all_activities(inchi_key)
        gene_set = set()
        for act in activities:
            if act.get('standard_type') in ("IC50", "AC50", "Ki"):
                target_chembl_id = act.get('target_chembl_id')
                if target_chembl_id:
                    target_info = self._get_target_cached(target_chembl_id)
                    gene = self._extract_gene_symbol(target_info) if target_info else '--'
                    if gene and gene != '--':
                        gene_set.add(gene)
        return gene_set

    def get_target_data(self, target_chembl_id: str) -> dict:
        """
        Fetch detailed target information using target_chembl_id.
        Uses cached data if available.
        """
        target_data = self._get_target_cached(target_chembl_id)
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

    @staticmethod
    def _to_float(value) -> float | None:
        try:
            parsed = float(value)
            if math.isnan(parsed) or math.isinf(parsed):
                return None
            return parsed
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalise_nm_value(value, units: str | None) -> float | None:
        parsed = ChEMBLClient._to_float(value)
        if parsed is None or parsed <= 0:
            return None
        normalized_units = str(units or '').strip().replace('μ', 'u').replace('µ', 'u').lower()
        if normalized_units == 'nm':
            return parsed
        if normalized_units == 'um':
            return parsed * 1_000.0
        if normalized_units == 'mm':
            return parsed * 1_000_000.0
        if normalized_units == 'pm':
            return parsed / 1_000.0
        if normalized_units == 'fm':
            return parsed / 1_000_000.0
        if normalized_units == 'm':
            return parsed * 1_000_000_000.0
        return None

    def get_aggregated_targets_by_inchikey(self, inchi_key: str, standard_types: tuple[str, ...] = ("IC50", "Ki", "AC50")) -> list[dict]:
        allowed_types = {str(t).strip().upper() for t in standard_types if str(t).strip()}
        activities = self._fetch_all_activities(inchi_key)
        if not activities:
            return []

        aggregated: dict[str, dict] = {}
        for act in activities:
            std_type = str(act.get('standard_type') or '').strip().upper()
            if std_type not in allowed_types:
                continue

            target_chembl_id = act.get('target_chembl_id')
            target_info = self._get_target_cached(target_chembl_id) if target_chembl_id else {}
            gene_symbol = self._extract_gene_symbol(target_info) if target_info else '--'
            if not gene_symbol or gene_symbol == '--':
                continue

            bucket = aggregated.setdefault(
                gene_symbol,
                {
                    'gene_symbol': gene_symbol,
                    'uniprot_ids': set(),
                    'target_chembl_ids': set(),
                    'target_names': set(),
                    'target_types': set(),
                    'target_organisms': set(),
                    'protein_target_classifications': set(),
                    'measurements': [],
                    'activity_summary': {},
                },
            )

            uniprot_id = self._extract_uniprot_id(target_info) if target_info else '--'
            if uniprot_id and uniprot_id != '--':
                bucket['uniprot_ids'].add(uniprot_id)
            if target_chembl_id:
                bucket['target_chembl_ids'].add(target_chembl_id)
            if act.get('target_pref_name'):
                bucket['target_names'].add(act.get('target_pref_name'))
            if act.get('target_organism'):
                bucket['target_organisms'].add(act.get('target_organism'))
            if target_info.get('target_type'):
                bucket['target_types'].add(target_info.get('target_type'))
            protein_class = self._extract_protein_classification(target_info) if target_info else '--'
            if protein_class and protein_class != '--':
                bucket['protein_target_classifications'].add(protein_class)

            measurement = {
                'activity_type': std_type,
                'activity_value': act.get('standard_value'),
                'activity_units': act.get('standard_units'),
                'relation': act.get('standard_relation'),
                'assay_chembl_id': act.get('assay_chembl_id'),
                'assay_type': act.get('assay_type'),
                'assay_description': act.get('assay_description'),
                'target_chembl_id': target_chembl_id,
            }
            normalized_nm = self._normalise_nm_value(act.get('standard_value'), act.get('standard_units'))
            if normalized_nm is not None:
                measurement['activity_value_nm'] = normalized_nm
            bucket['measurements'].append(measurement)

            per_type = bucket['activity_summary'].setdefault(
                std_type,
                {'count': 0, 'representative_value_nm': None, 'units': set()},
            )
            per_type['count'] += 1
            units = str(act.get('standard_units') or '').strip()
            if units:
                per_type['units'].add(units)
            if normalized_nm is not None and (
                per_type['representative_value_nm'] is None or normalized_nm < per_type['representative_value_nm']
            ):
                per_type['representative_value_nm'] = normalized_nm

        output = []
        for gene_symbol in sorted(aggregated.keys()):
            bucket = aggregated[gene_symbol]
            summary = {}
            for activity_type, data in bucket['activity_summary'].items():
                summary[activity_type] = {
                    'count': data['count'],
                    'representative_value_nm': data['representative_value_nm'],
                    'units': sorted(data['units']),
                }
            output.append(
                {
                    'gene_symbol': gene_symbol,
                    'uniprot_ids': sorted(bucket['uniprot_ids']),
                    'target_chembl_ids': sorted(bucket['target_chembl_ids']),
                    'target_names': sorted(bucket['target_names']),
                    'target_types': sorted(bucket['target_types']),
                    'target_organisms': sorted(bucket['target_organisms']),
                    'protein_target_classifications': sorted(bucket['protein_target_classifications']),
                    'measurements': bucket['measurements'],
                    'activity_summary': summary,
                    'measurement_count': len(bucket['measurements']),
                }
            )
        return output

if __name__ == "__main__":
    inchi_key = "ZKLPARSLTMPFCP-UHFFFAOYSA-N"
    obj = ChEMBLClient()
    print(type(obj.get_by_inchikey(inchi_key, "IC50")))
