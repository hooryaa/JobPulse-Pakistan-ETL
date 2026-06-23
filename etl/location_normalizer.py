from pathlib import Path
import csv
import re
from typing import Tuple, Optional


def load_gazetteer(path: Optional[str] = None):
    p = Path(path or 'config/pakistan_cities.csv')
    rows = []
    if not p.exists():
        return rows
    with p.open(encoding='utf8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({'city': r['city'].strip(), 'province': r.get('province','').strip(), 'country': r.get('country','').strip()})
    return rows


_GAZ = load_gazetteer()


def normalize_location(raw: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Normalize a raw location string into city, province, country, normalized_location

    Returns (city, province, country, normalized_location) or (None,..) if unknown.
    """
    if not raw:
        return (None, None, None, None)
    s = raw.strip()
    s_clean = re.sub(r'[\n\r]+', ' ', s)
    s_clean = re.sub(r'\s+', ' ', s_clean)
    s_lower = s_clean.lower()
    # direct match any gazetteer city
    for row in _GAZ:
        if row['city'].lower() in s_lower:
            normalized = row['city']
            return (row['city'], row['province'] or None, row['country'] or None, normalized)
    # heuristics: split by comma e.g., 'Lahore, Punjab, Pakistan'
    parts = [p.strip() for p in s_clean.split(',') if p.strip()]
    if len(parts) >= 1:
        city = parts[0]
        for row in _GAZ:
            if row['city'].lower() == city.lower():
                return (row['city'], row['province'] or None, row['country'] or None, row['city'])
        # otherwise return city as-is with None for province/country
        return (city, parts[1] if len(parts) > 1 else None, parts[-1] if len(parts) > 1 else None, city)

    return (None, None, None, None)


if __name__ == '__main__':
    print(normalize_location('Lahore, Punjab, Pakistan'))