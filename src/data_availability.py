"""Dataset availability registry.

Central knowledge of every local dataset the API depends on. Endpoints use
``require_dataset`` to fail fast with a structured 503 when a file is missing,
and ``/api/health`` exposes the full status map.

Design notes:
- Paths are resolved once at import time relative to this file (``src/``).
- Availability is cached per-process but re-checkable on demand (``refresh=``)
  because files may be dropped in while the server is running — datasets are
  often provisioned after deployment.
- The heavy loaders elsewhere (pandas/openpyxl/lru_cache) do their own caching
  of parsed content; this module only answers "does the file exist?".
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

_DATA_ROOT = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class DatasetSpec:
    key: str  # stable machine identifier, e.g. "creeds_signatures"
    label: str  # human-readable name for error messages
    relative_path: str  # path under src/data, forward slashes for portability


@dataclass
class DatasetStatus:
    key: str
    label: str
    path: str  # absolute path as string, for error messages
    available: bool
    missing_path: str | None = field(default=None)


_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec("creeds_signatures", "CREEDS disease signatures", "CREEDS/disease_signatures-v1.0.json"),
    DatasetSpec(
        "creeds_perturbations", "CREEDS single-drug perturbations", "CREEDS/single_drug_perturbations-v1.0.json"
    ),
    DatasetSpec("drugbank", "DrugBank full database", "drugBank/full database.xml"),
    DatasetSpec("geo", "GEO gene expression data", "geneCards/GEO DATA.xlsx"),
    DatasetSpec("ppi_xlsx", "PPI Excel sheets", "PPInteraction/xlsxData"),
    DatasetSpec("ppi_images", "PPI interaction images", "PPInteraction"),
)


class DatasetNotProvisionedError(RuntimeError):
    """Raised when a required local dataset file/directory is missing.

    Carries a user-safe message (no internals) suitable for HTTP 503 bodies.
    """

    def __init__(self, status: DatasetStatus) -> None:
        self.status = status
        super().__init__(
            f"Dataset '{status.label}' is not provisioned on this server. "
            f"Expected file: {status.missing_path}. Copy the dataset into place and retry."
        )


_lock = threading.Lock()
_status_cache: dict[str, DatasetStatus] | None = None


def _resolve(spec: DatasetSpec) -> DatasetStatus:
    path = (_DATA_ROOT / Path(*spec.relative_path.split("/"))).resolve()
    available = path.exists()
    return DatasetStatus(
        key=spec.key,
        label=spec.label,
        path=str(path),
        available=available,
        missing_path=None if available else str(path),
    )


def _statuses(refresh: bool) -> dict[str, DatasetStatus]:
    global _status_cache
    with _lock:
        if _status_cache is None or refresh:
            _status_cache = {spec.key: _resolve(spec) for spec in _SPECS}
        return _status_cache


def get_dataset_status(refresh: bool = False) -> dict[str, DatasetStatus]:
    """Return a mapping of dataset key -> status for all known datasets."""
    return _statuses(refresh)


def require_dataset(*keys: str, refresh: bool = False) -> None:
    """Raise :class:`DatasetNotProvisionedError` if any listed dataset is missing.

    Call at the top of endpoint handlers that depend on local files, so
    missing data produces a structured 503 instead of a 500 traceback.
    """
    statuses = _statuses(refresh)
    missing: list[DatasetStatus] = []
    for key in keys:
        status = statuses.get(key)
        if status is None:
            # Unknown key is a programming error — surface it loudly.
            raise KeyError(f"Unknown dataset key: {key}")
        if not status.available:
            missing.append(status)
    if missing:
        raise DatasetNotProvisionedError(missing[0])


def health_payload() -> dict:
    """Build the /api/health payload (always JSON-serialisable, never raises)."""
    statuses = _statuses(refresh=True)
    all_available = all(status.available for status in statuses.values())
    return {
        "status": "ok" if all_available else "degraded",
        "datasets": {
            status.key: {
                "label": status.label,
                "available": status.available,
                **({"expectedPath": status.missing_path} if status.missing_path else {}),
            }
            for status in statuses.values()
        },
    }


def dump_health(path: Path) -> None:
    """Write the health payload to a JSON file (CLI/admin helper)."""
    path.write_text(json.dumps(health_payload(), indent=2), encoding="utf-8")
