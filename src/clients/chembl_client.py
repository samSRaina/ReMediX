import logging
import math
import re
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

# Upper bound on activities fetched per molecule for the UNFILTERED path
# (bioactivity table "all types" view). Well-studied compounds have thousands
# of rows; beyond this the payload is huge and latency dominates. When the cap
# is hit a warning is logged so truncation is visible, never silent.
MAX_ACTIVITIES_PER_MOLECULE = 2000

# Upper bound for a FILTERED (typed) fetch. The server-side standard_type__in
# filter already shrinks the result set, so the cap can be more generous while
# still bounding payload/latency for pathological molecules.
MAX_TYPED_ACTIVITIES_PER_MOLECULE = 5000

# Default activity types used by the gene-set / scoring paths.
PHARMACOLOGY_ACTIVITY_TYPES = ("IC50", "Ki", "AC50")

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
MAX_MOLECULE_CACHE_ENTRIES = 2_000

# ChEMBL stores these standard types with this exact casing. Canonicalisation
# maps whatever the caller sends (ic50, ki, KI, "ic50, ki") onto this.
_CANONICAL_ACTIVITY_TYPES = {"IC50": "IC50", "KI": "Ki", "AC50": "AC50"}


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
                    raise ConnectionError(f"ChEMBL API is currently unavailable: {e}") from e
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


def parse_activity_types(standard_type) -> tuple[str, ...]:
    """Canonicalise a user-supplied standard_type filter.

    Accepts None, a single value ("IC50"), or multi-values ("ic50,ki",
    "IC50|AC50", "ki; ic50"). Casing is irrelevant; separators are
    comma, semicolon, pipe or whitespace. Unknown types pass through
    upper-cased (the server may know them) but well-known types are
    normalised to ChEMBL's exact spelling (e.g. KI -> Ki).

    Returns a tuple sorted for stable cache keys; empty tuple means
    "no filter".
    """
    if not standard_type:
        return ()
    if isinstance(standard_type, (list, tuple, set)):
        tokens = [str(t) for t in standard_type]
    else:
        tokens = re.split(r"[,;|\s]+", str(standard_type))
    canonical = set()
    for token in tokens:
        token = token.strip().upper()
        if not token:
            continue
        canonical.add(_CANONICAL_ACTIVITY_TYPES.get(token, token))
    return tuple(sorted(canonical))


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
    # inchi_key -> molecule_chembl_id (or None when the compound is unknown).
    _molecule_cache = _BoundedCache(MAX_MOLECULE_CACHE_ENTRIES)

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

    # ------------------------------------------------------------------
    # Molecule resolution
    # ------------------------------------------------------------------
    def _resolve_molecule_chembl_id(self, inchi_key: str) -> str | None:
        """Map a standard InChIKey to its molecule_chembl_id (cached)."""
        if not inchi_key:
            return None
        if self._molecule_cache.contains(inchi_key):
            return self._molecule_cache.get(inchi_key)

        try:
            # Slice to one record: we only need the identifier, and this keeps
            # the molecule payload (which is fat) to a single record.
            compound = list(self.molecule.filter(molecule_structures__standard_inchi_key=inchi_key)[:1])
        except Exception as e:
            logger.error(f"Error fetching molecule for {inchi_key}: {e}")
            return None  # do not cache failures; a later retry may succeed

        chembl_id = compound[0].get("molecule_chembl_id") if compound else None
        self._molecule_cache.put(inchi_key, chembl_id)
        return chembl_id

    # ------------------------------------------------------------------
    # Activity fetching
    # ------------------------------------------------------------------
    def _fetch_raw_activities(self, chembl_id: str) -> list:
        """Fetch a molecule's activities, unfiltered, bounded by MAX_ACTIVITIES_PER_MOLECULE.

        When the cap truncates (server total_count > cap), a warning is
        logged so truncation is visible, never silent.
        """
        try:
            sliced = self.activity.filter(molecule_chembl_id=chembl_id)[:MAX_ACTIVITIES_PER_MOLECULE]
            activities = list(sliced)
        except Exception as e:
            logger.error(f"Error fetching activities for {chembl_id}: {e}")
            return []

        self._warn_if_truncated(chembl_id, sliced, MAX_ACTIVITIES_PER_MOLECULE)
        return activities

    def _fetch_typed_activities(self, chembl_id: str, activity_types: tuple[str, ...]) -> list:
        """Fetch activities for the given standard_types ONLY, server-side.

        The standard_type filter is pushed down to the ChEMBL API via
        standard_type__in, so the client fetches exactly the rows it needs
        (complete — no cap-induced silent truncation of a type) instead of
        fetching every activity record and discarding ~98% locally.
        """
        try:
            sliced = self.activity.filter(
                molecule_chembl_id=chembl_id,
                standard_type__in=list(activity_types),
            )[:MAX_TYPED_ACTIVITIES_PER_MOLECULE]
            activities = list(sliced)
        except Exception as e:
            logger.error(f"Error fetching activities for {chembl_id} (types={activity_types}): {e}")
            return []

        self._warn_if_truncated(chembl_id, sliced, MAX_TYPED_ACTIVITIES_PER_MOLECULE)
        return activities

    @staticmethod
    def _warn_if_truncated(chembl_id: str, qs, cap: int) -> None:
        """Log a visible warning when the slice cap cut results short."""
        try:
            total = qs.query.api_total_count
        except AttributeError:
            return
        if total and total > cap:
            logger.warning(
                f"ChEMBL activities for {chembl_id} truncated at {cap} of {total} rows"
            )

    def _prefetch_targets(self, activities: list) -> None:
        """Batch-fetch every target referenced by these activities (parallel chunks)."""
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

    def _activities_for_types(self, inchi_key: str, activity_types: tuple[str, ...]) -> list:
        """Cached activity fetch. Empty tuple = all types (unfiltered)."""
        cache_key = (inchi_key, activity_types)
        cached = self._activities_cache.get(cache_key)
        if cached is not None:
            return cached

        chembl_id = self._resolve_molecule_chembl_id(inchi_key)
        if not chembl_id:
            # Unknown compound: cache the empty answer keyed per type-set so
            # repeated asks stay free; molecule-lookup failures are never
            # cached, so a transient API error stays retryable.
            self._activities_cache.put(cache_key, [])
            return []

        if activity_types:
            activities = self._fetch_typed_activities(chembl_id, activity_types)
        else:
            activities = self._fetch_raw_activities(chembl_id)

        if activities:
            self._prefetch_targets(activities)

        self._activities_cache.put(cache_key, activities)
        return activities

    # Kept for backwards compatibility with earlier call sites.
    def _fetch_all_activities(self, inchi_key: str) -> list:
        """Fetch ALL activities for a molecule (unfiltered, bounded, cached)."""
        return self._activities_for_types(inchi_key, ())

    def has_bioactivity_data(self, inchi_key: str) -> bool:
        """Cheap existence check: does this compound have ANY activity rows?

        One molecule lookup (cached) + a single activity request returning at
        most one row — no full fetch, no enrichment.
        """
        chembl_id = self._resolve_molecule_chembl_id(inchi_key)
        if not chembl_id:
            return False
        try:
            return bool(list(self.activity.filter(molecule_chembl_id=chembl_id)[:1]))
        except Exception as e:
            logger.error(f"Error checking activity existence for {chembl_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Target helpers
    # ------------------------------------------------------------------
    def _get_target_cached(self, target_chembl_id: str) -> dict:
        """Fetch target data with caching to avoid repeated API calls."""
        cached = self._target_cache.get(target_chembl_id)
        if cached is None:
            try:
                cached = self.target.get(target_chembl_id) or {}
            except Exception as e:
                # Degrade to '--' enrichment instead of failing the whole
                # bioactivity response; do NOT cache so a retry can succeed.
                logger.warning(f"Target fetch failed for {target_chembl_id}: {e}")
                return {}
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
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

    def get_by_inchikey(self, inchi_key: str, standard_type=None, include_target_details: bool = False, only_with_target_type: bool = False) -> list:
        """Enriched activity rows for a compound, optionally filtered by standard_type.

        The standard_type filter is pushed down to the ChEMBL API
        (standard_type__in), so filtered queries return the COMPLETE set of
        matching rows instead of a cap-truncated slice of an unfiltered
        fetch. Callers may pass "IC50", "ic50,ki", ["IC50", "Ki"], etc.
        """
        activity_types = parse_activity_types(standard_type)
        activities = self._activities_for_types(inchi_key, activity_types)
        if not activities:
            return []

        # Defensive residue filter: the server already filtered, but keep the
        # guarantee that every returned row matches the requested type set
        # exactly (guards against type-spelling drift between layers).
        if activity_types:
            allowed = set(activity_types)
            activities = [act for act in activities if act.get('standard_type') in allowed]

        act_data = []
        for act in activities:
            entry = self._enrich_activity(act, include_target_details)
            if only_with_target_type and entry['target_type'] == '--':
                continue
            act_data.append(entry)

        return act_data

    def get_gene_set(self, inchi_key: str) -> set:
        """Collect all valid gene symbols for IC50, AC50, and Ki.

        Uses the typed (server-side filtered) cached fetch — complete and
        cheaper than an unfiltered fetch.
        """
        activity_types = parse_activity_types(PHARMACOLOGY_ACTIVITY_TYPES)
        activities = self._activities_for_types(inchi_key, activity_types)
        gene_set = set()
        for act in activities:
            target_chembl_id = act.get('target_chembl_id')
            if target_chembl_id:
                target_info = self._get_target_cached(target_chembl_id)
                gene = self._extract_gene_symbol(target_info) if target_info else '--'
                if gene and gene != '--':
                    gene_set.add(gene)
        return gene_set

    def get_target_data(self, target_chembl_id: str) -> dict:
        """Fetch detailed target information using target_chembl_id.

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

    def get_aggregated_targets_by_inchikey(self, inchi_key: str, standard_types: tuple[str, ...] = PHARMACOLOGY_ACTIVITY_TYPES) -> list[dict]:
        """Aggregate pharmacology rows per gene symbol, using the typed fetch."""
        allowed_types = set(parse_activity_types(standard_types))
        if not allowed_types:
            allowed_types = set(parse_activity_types(PHARMACOLOGY_ACTIVITY_TYPES))

        activity_types = tuple(sorted(allowed_types))
        activities = self._activities_for_types(inchi_key, activity_types)
        if not activities:
            return []

        # Measurements report activity_type upper-cased (historical contract:
        # scoring and the frontend compare case-insensitively), so match on
        # the upper-cased form of the canonical spellings.
        allowed_upper = {t.upper() for t in allowed_types}

        aggregated: dict[str, dict] = {}
        for act in activities:
            std_type = str(act.get('standard_type') or '').strip().upper()
            if std_type not in allowed_upper:
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
    # Small live debug probe: python -m src.clients.chembl_client
    import collections

    inchi_key = "ZZUFCTLCJUWOSV-UHFFFAOYSA-N"  # FUROSIDE
    obj = ChEMBLClient()

    for label, types in [
        ("unfiltered", None),
        ("IC50", "IC50"),
        ("Ki", "ki"),          # lowercase on purpose: exercises canonicalisation
        ("AC50", "ac50"),
        ("IC50+Ki+AC50", "ic50, ki, ac50"),
    ]:
        rows = obj.get_by_inchikey(inchi_key, types)
        dist = collections.Counter(r["standard_type"] for r in rows)
        print(f"{label:>12}: {len(rows):4d} rows  {dict(dist)}")

    genes = obj.get_gene_set(inchi_key)
    print(f"gene_set: {len(genes)} genes -> {sorted(genes)[:10]} ...")

    agg = obj.get_aggregated_targets_by_inchikey(inchi_key)
    print(f"aggregated_targets: {len(agg)} genes, "
          f"{sum(g['measurement_count'] for g in agg)} measurements")
