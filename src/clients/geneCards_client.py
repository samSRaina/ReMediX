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
def get_geo_data() -> list[dict]:
    """Read Excel once, cache in memory for subsequent calls."""
    df = pd.read_excel(GEO_DATA, sheet_name="REFER THIS ")
    return _clean_nan(df.to_dict(orient="records"))

