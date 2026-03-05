from pathlib import Path
from functools import lru_cache
import math
import pandas as pd

GEO_DATA= Path(__file__).parent.parent/'data'/'geneCards'/'GEO DATA.xlsx'

def _clean_nan(records: list[dict]) -> list[dict]:
    """Replace float NaN/inf values with None for JSON compatibility."""
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                record[key] = None
    return records

@lru_cache(maxsize=1)
def _load_geo_data() -> list[dict]:
    """Read Excel once, cache in memory for subsequent calls."""
    df = pd.read_excel(GEO_DATA, sheet_name="REFER THIS ")
    return _clean_nan(df.to_dict(orient="records"))


def get_geo_data(page: int = 1, page_size: int = 50, search: str | None = None) -> dict:
    """Return paginated and optionally filtered GEO data."""
    all_data = _load_geo_data()

    if search:
        search_lower = search.lower()
        all_data = [
            row for row in all_data
            if row.get("Gene.symbol") and search_lower in str(row["Gene.symbol"]).lower()
        ]

    total = len(all_data)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "data": all_data[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


