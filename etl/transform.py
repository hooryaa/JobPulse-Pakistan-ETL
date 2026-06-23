import json
from pathlib import Path
from typing import List, Dict
import csv
import re
from datetime import datetime

from etl.utils import clean_text
from etl import skills as skills_module
from etl.location_normalizer import normalize_location


def parse_salary_from_text(text: str):
    if not text:
        return (None, None, None, None)
    # look for PKR or Rs or numbers with k
    m = re.search(r"(PKR|Rs\.?|Rs)\s*([0-9,]+)(?:\s*-\s*([0-9,]+))?", text, re.I)
    if m:
        cur = m.group(1)
        a = int(m.group(2).replace(',', ''))
        b = int(m.group(3).replace(',', '')) if m.group(3) else a
        period = 'monthly' if re.search(r'month', text, re.I) else ('yearly' if re.search(r'year|yr', text, re.I) else None)
        return (a, b, cur, period)
    m2 = re.search(r"([0-9]+)k", text, re.I)
    if m2:
        a = int(m2.group(1)) * 1000
        return (a, a, 'PKR', None)
    return (None, None, None, None)


def discover_raw_files(root: Path) -> List[Path]:
    files = list(root.rglob('*.json'))
    return files


def transform_raw_to_staging(raw_root: Path, staging_dir: Path):
    staging_dir.mkdir(parents=True, exist_ok=True)
    postings_path = staging_dir / 'job_postings.csv'
    skills_path = staging_dir / 'job_skills.csv'

    skills_master = skills_module.load_skills_master()

    postings_fields = ['posting_id','source','title','company','city','province','country','normalized_location','salary_min','salary_max','salary_currency','salary_period','skills','content_hash','raw_path','fetched_at']

    postings_out = []
    skills_out = []

    for p in discover_raw_files(raw_root):
        try:
            obj = json.loads(p.read_text(encoding='utf8'))
        except Exception:
            continue
        posting_id = obj.get('posting_id')
        source = 'rozee'
        title = clean_text(obj.get('title'))
        company = clean_text(obj.get('company'))
        desc = clean_text(obj.get('description'))
        raw_loc = obj.get('location')
        city, province, country, normalized = normalize_location(raw_loc) if raw_loc else (None, None, None, None)
        # fallback: try to find city in description
        if not city and desc:
            for cand in ['Lahore','Karachi','Islamabad','Rawalpindi','Faisalabad','Multan','Peshawar','Quetta']:
                if cand.lower() in desc.lower():
                    city = cand
                    normalized = cand
                    country = 'Pakistan'
                    break

        # salary: prefer extracted fields
        smin = obj.get('salary_min')
        smax = obj.get('salary_max')
        scur = obj.get('salary_currency')
        speriod = obj.get('salary_period')
        if not smin and desc:
            a,b,cur,period = parse_salary_from_text(desc)
            if a:
                smin, smax, scur, speriod = a,b,cur,period

        # skills: from title + description
        combined = ' '.join(x for x in [title or '', desc or ''] if x)
        extracted = skills_module.extract_skills(combined, skills_master, max_skills=6)

        # Fallback: look for explicit 'skills' or 'requirements' list in description
        if not extracted and desc:
            m = re.search(r"(?:skills?|requirements?)\s*[:\-]\s*(.+)", desc, re.I)
            if m:
                cand = m.group(1)
                parts = re.split(r'[;,|\\n]', cand)
                parts = [p.strip() for p in parts if p.strip()]
                # match parts against skills_master aliases/canonical
                for part in parts:
                    for s in skills_master:
                        aliases = [a.strip().lower() for a in s['aliases']] + [s['canonical'].lower()]
                        if part.lower() in aliases or any(part.lower() in a for a in aliases):
                            if s['canonical'] not in extracted:
                                extracted.append(s['canonical'])

        content_hash = obj.get('content_hash')
        fetched_at = obj.get('fetched_at')

        row = {
            'posting_id': posting_id,
            'source': source,
            'title': title,
            'company': company,
            'city': city,
            'province': province,
            'country': country or 'Pakistan',
            'normalized_location': normalized,
            'salary_min': smin,
            'salary_max': smax,
            'salary_currency': scur,
            'salary_period': speriod,
            'skills': ';'.join(extracted) if extracted else None,
            'content_hash': content_hash,
            'raw_path': str(p),
            'fetched_at': fetched_at
        }
        postings_out.append(row)
        for sk in extracted:
            skills_out.append({'posting_id': posting_id, 'skill': sk})

    # write CSVs
    with postings_path.open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=postings_fields)
        writer.writeheader()
        for r in postings_out:
            writer.writerow(r)

    with skills_path.open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['posting_id','skill'])
        writer.writeheader()
        for r in skills_out:
            writer.writerow(r)

    # Validation summary
    total_postings = len(postings_out)
    postings_with_skills = len([r for r in postings_out if r.get('skills')])
    total_skill_rows = len(skills_out)
    print(f'Transform summary: total_postings={total_postings}, postings_with_skills={postings_with_skills}, total_skill_rows={total_skill_rows}')

    return postings_path, skills_path


def generate_simple_report(staging_dir: Path, out_dir: Path):
    postings_path = staging_dir / 'job_postings.csv'
    skills_path = staging_dir / 'job_skills.csv'
    import pandas as pd
    if not postings_path.exists():
        return None
    df = pd.read_csv(postings_path)
    df_sk = pd.read_csv(skills_path) if skills_path.exists() else None

    total = len(df)
    top_sk = df_sk['skill'].value_counts().head(10).to_dict() if df_sk is not None else {}
    top_cities = df['city'].fillna('Unknown').value_counts().head(10).to_dict()
    remote_pct = 0

    out = []
    out.append('# JobPulse Pakistan Report')
    out.append(f'Jobs analyzed: {total}')
    out.append('')
    out.append('Top Skills')
    i = 1
    for k,v in top_sk.items():
        out.append(f'{i}. {k} ({v} postings)')
        i += 1
    out.append('')
    out.append('Top Cities')
    i = 1
    for k,v in top_cities.items():
        out.append(f'{i}. {k} ({v} postings)')
        i += 1

    release_dir = Path('docs/releases') / datetime.utcnow().strftime('%Y-%m-%d')
    release_dir.mkdir(parents=True, exist_ok=True)
    report_path = release_dir / 'jobpulse_pakistan_report.md'
    report_path.write_text('\n'.join(out), encoding='utf8')
    return report_path


if __name__ == '__main__':
    raw_root = Path('data/raw/rozee')
    staging_dir = Path('data/staging')
    postings_path, skills_path = transform_raw_to_staging(raw_root, staging_dir)
    print('Wrote staging:', postings_path, skills_path)
    rpt = generate_simple_report(staging_dir, Path('docs/releases'))
    print('Report written to:', rpt)
