from pathlib import Path
from lxml import etree
from typing import Optional
import logging
from threading import Lock
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DrugBankClient:
    NS = {'db': 'http://www.drugbank.ca'}
    DEFAULT_XML_PATH = Path(__file__).resolve().parent.parent / 'data' / 'drugBank' / 'full database.xml'
    DEFAULT_INDEX_CACHE_PATH = (
        Path(__file__).resolve().parent.parent / 'data' / 'drugBank' / 'drugbank_inchikey_index.pkl'
    )
    _index_lock = Lock()
    _index_by_xml_path: dict[str, dict[str, dict]] = {}

    def __init__(self, xml_path: Path = None, index_cache_path: Path = None):
        self.xml_path = xml_path or self.DEFAULT_XML_PATH
        self.index_cache_path = index_cache_path or self.DEFAULT_INDEX_CACHE_PATH

    @staticmethod
    def _normalize_inchikey(inchikey: str) -> str:
        return (inchikey or '').strip().upper()

    def _cache_metadata(self) -> dict[str, int | str]:
        stat = self.xml_path.stat()
        return {
            'xml_path': str(self.xml_path.resolve()),
            'xml_mtime_ns': stat.st_mtime_ns,
            'xml_size': stat.st_size,
        }

    def _extract_index_from_cache_payload(self, payload: object) -> Optional[dict[str, dict]]:
        # Support both legacy "raw index dict" caches and newer metadata payloads.
        if not isinstance(payload, dict):
            return None

        # New format: {"metadata": ..., "index": {...}}
        if "index" in payload:
            index = payload.get("index")
            if isinstance(index, dict):
                return index
            return None

        # Legacy format: payload is already the index map.
        if all(isinstance(value, dict) for value in payload.values()):
            return payload

        return None

    def _load_cached_index(self) -> Optional[dict[str, dict]]:
        if not self.index_cache_path.exists():
            return None

        try:
            with self.index_cache_path.open('rb') as fh:
                payload = pickle.load(fh)
        except Exception as exc:
            logger.warning("Failed to read DrugBank cache file (%s): %s", self.index_cache_path, exc)
            return None

        index = self._extract_index_from_cache_payload(payload)
        if index is None:
            logger.warning(
                "DrugBank cache file exists but has an unsupported format (%s); rebuilding index",
                self.index_cache_path,
            )
            return None

        logger.info("Loaded DrugBank index cache from %s", self.index_cache_path)
        return index

    def _save_cached_index(self, index: dict[str, dict]) -> None:
        try:
            self.index_cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {'metadata': self._cache_metadata(), 'index': index}
            with self.index_cache_path.open('wb') as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            logger.warning("Failed to write DrugBank cache file (%s): %s", self.index_cache_path, exc)

    def _validate_xml_source(self) -> None:
        if not self.xml_path.exists():
            raise RuntimeError(
                f"DrugBank XML not found at '{self.xml_path}'. Ensure data files are present."
            )

        stat = self.xml_path.stat()
        if stat.st_size == 0:
            raise RuntimeError(
                f"DrugBank XML is empty at '{self.xml_path}'. If this repo uses Git LFS, run 'git lfs pull'."
            )

        # Git LFS pointer files are tiny text manifests, not real XML payloads.
        try:
            with self.xml_path.open('rb') as fh:
                prefix = fh.read(128)
        except OSError as exc:
            raise RuntimeError(f"Unable to read DrugBank XML at '{self.xml_path}': {exc}") from exc

        if prefix.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise RuntimeError(
                f"DrugBank XML at '{self.xml_path}' is a Git LFS pointer. Run 'git lfs pull' to fetch real data."
            )

    def _build_index(self) -> dict[str, dict]:
        """Build a one-time in-memory index for fast lookups."""
        cached_index = self._load_cached_index()
        if cached_index is not None:
            return cached_index

        self._validate_xml_source()

        logger.info("Building DrugBank index from %s", self.xml_path)
        index: dict[str, dict] = {}
        try:
            for _, elem in etree.iterparse(
                str(self.xml_path),
                events=('end',),
                tag='{http://www.drugbank.ca}drug',
            ):
                inchikey, drug_data = self._extract_drug_data_with_inchikey(elem)
                if inchikey and inchikey not in index:
                    index[inchikey] = drug_data

                elem.clear()

                # Release processed siblings to keep iterparse memory footprint stable.
                parent = elem.getparent()
                if parent is not None:
                    while elem.getprevious() is not None:
                        del parent[0]
        except etree.XMLSyntaxError as exc:
            raise RuntimeError(
                f"DrugBank XML parse failed for '{self.xml_path}': {exc}. "
                "If this file is tracked with Git LFS, run 'git lfs pull'."
            ) from exc

        logger.info("DrugBank index built with %d InChIKey entries", len(index))
        self._save_cached_index(index)
        return index

    def _get_index(self) -> dict[str, dict]:
        xml_path_key = str(self.xml_path.resolve())
        existing_index = self.__class__._index_by_xml_path.get(xml_path_key)
        if existing_index is not None:
            return existing_index

        with self.__class__._index_lock:
            existing_index = self.__class__._index_by_xml_path.get(xml_path_key)
            if existing_index is None:
                existing_index = self._build_index()
                self.__class__._index_by_xml_path[xml_path_key] = existing_index
        return existing_index

    def search_drug_by_inchikey(self, inchikey: str) -> Optional[dict]:
        normalized = self._normalize_inchikey(inchikey)
        if not normalized:
            return None
        return self._get_index().get(normalized)

    def _extract_drug_data_with_inchikey(self, drug_elem) -> tuple[Optional[str], dict]:
        """Extract relevant data and normalized InChIKey from a drug XML element."""
        data = {}
        inchikey: Optional[str] = None

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
                    kind_text = (kind.text or '').strip()
                    value_text = value.text
                    if not kind_text:
                        continue

                    prop_name = kind_text.lower().replace(' ', '_').replace('-', '_')
                    data[prop_name] = value_text

                    if kind_text == 'InChIKey' and value_text and inchikey is None:
                        inchikey = self._normalize_inchikey(value_text)

        return inchikey, data

    def _extract_drug_data(self, drug_elem) -> dict:
        # Keep compatibility for existing imports/debug scripts.
        _, data = self._extract_drug_data_with_inchikey(drug_elem)

        return data


if __name__ == "__main__":
    client = DrugBankClient()
    result = client.search_drug_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    print(result)

