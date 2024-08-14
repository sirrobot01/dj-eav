from datetime import datetime, date
from types import SimpleNamespace

DATA_TYPES_MAP = {
    'string': str,
    'integer': int,
    'float': float,
    'boolean': bool,
    'date': date,
    'datetime': datetime,
    'json': dict,
    'file': str
}

def dict_to_object(d):
    if isinstance(d, dict):
        for key, value in d.items():
            d[key] = dict_to_object(value)
        return SimpleNamespace(**d)
    elif isinstance(d, list):
        return [dict_to_object(item) if isinstance(item, dict) else item for item in d]
    return d

