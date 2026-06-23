from pathlib import Path
import csv
from typing import List, Dict, Optional
import re
from rapidfuzz import process, fuzz


def load_skills_master(path: Optional[str] = None) -> List[Dict]:
    p = Path(path or 'config/skills_master.csv')
    skills = []
    if not p.exists():
        return skills
    with p.open(encoding='utf8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            aliases = [a.strip() for a in row.get('aliases', '').split(';') if a.strip()]
            skills.append({'canonical': row['canonical_skill'].strip(), 'aliases': aliases, 'category': row.get('category', '').strip()})
    return skills


def normalize_skill(s: str) -> str:
    return re.sub(r"\s+", ' ', s.strip().lower())


def extract_skills(text: str, skills_master: List[Dict], max_skills: int = 5) -> List[str]:
    """Extract skills from text using exact and fuzzy matching.

    Returns canonical skill names.
    """
    if not text:
        return []
    txt = text.lower()
    found = {}
    # exact alias match
    for s in skills_master:
        for alias in s['aliases'] + [s['canonical']]:
            if alias and alias.lower() in txt:
                found[s['canonical']] = found.get(s['canonical'], 0) + 2
    # token fuzzy match on ngrams
    tokens = re.findall(r"[a-zA-Z+#.]+", txt)
    joined = ' '.join(tokens)
    choices = [s['canonical'] for s in skills_master]
    if choices:
        matches = process.extract(joined, choices, scorer=fuzz.token_sort_ratio, limit=20)
        for match, score, _ in matches:
            if score >= 80:
                found[match] = found.get(match, 0) + int(score / 20)

    # rank by score
    ranked = sorted(found.items(), key=lambda x: x[1], reverse=True)
    return [r[0] for r in ranked[:max_skills]]


if __name__ == '__main__':
    skills = load_skills_master()
    sample = 'We are looking for Python developers with SQL and AWS experience, familiarity with PostgreSQL and Docker.'
    print(extract_skills(sample, skills))
