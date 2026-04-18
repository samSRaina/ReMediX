import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)


class ChEMBLClient:
    # Class-level caches for persistence across requests
    _target_cache = {}
    _activities_cache = {}
    _molecule_cache = {}

    ACTIVITY_URL = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
    MOLECULE_URL = "https://www.ebi.ac.uk/chembl/api/data/molecule.json"
    TARGET_URL_TEMPLATE = "https://www.ebi.ac.uk/chembl/api/data/target/{target_chembl_id}.json"

    @staticmethod
    def _parse_standard_type_filter(standard_type: str | None) -> set[str]:
        if not standard_type:
            return set()

        # Accept one or many values: "IC50", "ic50,ki", or "ac50/ic50/ki".
        tokens = [token.strip().upper() for token in re.split(r"[,/|]+", standard_type) if token.strip()]
        return set(tokens)

    def _resolve_molecule_chembl_id(self, inchi_key: str) -> str | None:
        if not inchi_key:
            return None
        normalized = inchi_key.strip().upper()
        if normalized in self._molecule_cache:
            return self._molecule_cache[normalized]

        params = {
            "molecule_structures__standard_inchi_key": normalized,
            "limit": 1,
        }

        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(self.MOLECULE_URL, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
                molecules = payload.get("molecules", [])
                chembl_id = molecules[0].get("molecule_chembl_id") if molecules else None
                self._molecule_cache[normalized] = chembl_id
                return chembl_id
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))

        raise ConnectionError(
            f"Failed to resolve ChEMBL molecule ID from InChIKey {normalized}"
        ) from last_error

    def _fetch_target_by_id(self, target_chembl_id: str) -> dict:
        """Fetch one target record from REST API; return empty dict on miss/failure."""
        if not target_chembl_id:
            return {}

        url = self.TARGET_URL_TEMPLATE.format(target_chembl_id=target_chembl_id)
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning(f"Error fetching target {target_chembl_id}: {exc}")
            return {}

    def _get_target_cached(self, target_chembl_id: str) -> dict:
        if target_chembl_id not in self._target_cache:
            self._target_cache[target_chembl_id] = self._fetch_target_by_id(target_chembl_id)
        return self._target_cache[target_chembl_id]

    def _batch_fetch_targets(self, target_ids: list[str]) -> None:
        uncached_ids = [tid for tid in target_ids if tid and tid not in self._target_cache]
        for tid in uncached_ids:
            self._target_cache[tid] = self._fetch_target_by_id(tid)

    def _extract_protein_classification(self, target_data: dict) -> str:
        value = target_data.get("protein_classification")
        return value if value else "--"

    def _extract_gene_symbol(self, target_data: dict) -> str:
        for comp in target_data.get("target_components", []):
            for syn in comp.get("target_component_synonyms", []):
                if syn.get("syn_type") == "GENE_SYMBOL":
                    value = syn.get("component_synonym")
                    return value if value else "--"
        return "--"

    def _extract_uniprot_id(self, target_data: dict) -> str:
        for comp in target_data.get("target_components", []):
            accession = comp.get("accession")
            if accession:
                return accession
        return "--"

    def _request_activity_page(self, molecule_chembl_id: str, limit: int, offset: int) -> dict:
        params = {
            "molecule_chembl_id": molecule_chembl_id,
            "limit": limit,
        }
        # First page is more reliable when offset is omitted.
        if offset > 0:
            params["offset"] = offset

        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(self.ACTIVITY_URL, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))

        raise ConnectionError(f"Failed to query activity data from ChEMBL for {molecule_chembl_id}") from last_error

    def _fetch_activities_paginated(self, molecule_chembl_id: str, page_size: int = 20, max_pages: int = 120) -> list[dict]:
        activities: list[dict] = []
        offset = 0

        for _ in range(max_pages):
            try:
                payload = self._request_activity_page(molecule_chembl_id, page_size, offset)
            except ConnectionError:
                # Keep partial data if upstream fails after at least one successful page.
                if activities:
                    logger.warning(
                        f"ChEMBL paging interrupted for {molecule_chembl_id} at offset={offset}; returning partial data"
                    )
                    break
                raise
            page_rows = payload.get("activities", [])
            if not page_rows:
                break

            activities.extend(page_rows)
            page_meta = payload.get("page_meta", {})
            if not page_meta.get("next"):
                break

            offset += page_size

        return activities

    def _fetch_all_activities(self, inchi_key: str) -> list[dict]:
        normalized = (inchi_key or "").strip().upper()
        if normalized in self._activities_cache:
            return self._activities_cache[normalized]

        molecule_chembl_id = self._resolve_molecule_chembl_id(normalized)
        if not molecule_chembl_id:
            self._activities_cache[normalized] = []
            return []

        activities = self._fetch_activities_paginated(molecule_chembl_id)

        unique_target_ids = list({act.get("target_chembl_id") for act in activities if act.get("target_chembl_id")})
        if unique_target_ids:
            chunk_size = 50
            chunks = [unique_target_ids[i : i + chunk_size] for i in range(0, len(unique_target_ids), chunk_size)]
            with ThreadPoolExecutor(max_workers=8) as executor:
                executor.map(self._batch_fetch_targets, chunks)

        self._activities_cache[normalized] = activities
        return activities

    def _enrich_activity(self, act: dict, include_target_details: bool = False) -> dict:
        target_chembl_id = act.get("target_chembl_id")
        target_info = self._get_target_cached(target_chembl_id) if target_chembl_id else {}
        target_type = target_info.get("target_type") or None

        gene_symbol = self._extract_gene_symbol(target_info) if target_info else "--"
        uniprot_id = self._extract_uniprot_id(target_info) if target_info else "--"
        protein_classification = self._extract_protein_classification(target_info) if target_info else "--"

        activity_entry = {
            "target_chembl_id": target_chembl_id or "--",
            "target_name": act.get("target_pref_name") or "--",
            "target_type": target_type or "--",
            "target_organism": act.get("target_organism") or "--",
            "gene_symbol": gene_symbol,
            "uniprot_id": uniprot_id,
            "standard_type": act.get("standard_type") or "--",
            "standard_value": act.get("standard_value") or "--",
            "standard_units": act.get("standard_units") or "--",
            "protein_target_classification": protein_classification,
        }

        if include_target_details and target_chembl_id:
            activity_entry["target_details"] = self.get_target_data(target_chembl_id)

        return activity_entry

    def get_by_inchikey(
        self,
        inchi_key: str,
        standard_type: str = None,
        include_target_details: bool = False,
        only_with_target_type: bool = False,
    ) -> list[dict]:
        activities = self._fetch_all_activities(inchi_key)
        if not activities:
            return []

        accepted_types = self._parse_standard_type_filter(standard_type)
        if accepted_types:
            activities = [
                act
                for act in activities
                if (act.get("standard_type") or "").strip().upper() in accepted_types
            ]

        act_data = []
        for act in activities:
            entry = self._enrich_activity(act, include_target_details)
            if only_with_target_type and entry["target_type"] == "--":
                continue
            act_data.append(entry)

        return act_data

    def get_gene_set(self, inchi_key: str) -> set[str]:
        activities = self._fetch_all_activities(inchi_key)
        gene_set = set()
        accepted_types = {"IC50", "AC50", "KI"}
        for act in activities:
            if (act.get("standard_type") or "").strip().upper() in accepted_types:
                target_chembl_id = act.get("target_chembl_id")
                if not target_chembl_id:
                    continue
                target_info = self._get_target_cached(target_chembl_id)
                gene = self._extract_gene_symbol(target_info) if target_info else "--"
                if gene and gene != "--":
                    gene_set.add(gene)
        return gene_set

    def get_target_data(self, target_chembl_id: str) -> dict:
        target_data = self._get_target_cached(target_chembl_id)
        if not target_data:
            return {}

        accessions = [
            comp.get("accession")
            for comp in target_data.get("target_components", [])
            if comp.get("accession")
        ]

        return {
            "protein_name": target_data.get("pref_name"),
            "protein_classification": target_data.get("target_type"),
            "uniprot_accession": accessions[0] if len(accessions) == 1 else accessions if accessions else None,
        }


if __name__ == "__main__":
    inchi_key = "ZKLPARSLTMPFCP-UHFFFAOYSA-N"
    obj = ChEMBLClient()
    print(type(obj.get_by_inchikey(inchi_key, "IC50")))
