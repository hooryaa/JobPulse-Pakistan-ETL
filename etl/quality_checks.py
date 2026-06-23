import logging
import json
from pathlib import Path
from typing import List, Dict

import pandas as pd

LOGGER = logging.getLogger("jobpulse.quality")


def run_quality_checks(df: pd.DataFrame) -> Dict:
    rows = len(df)
    duplicates = df.duplicated(subset=['posting_id']).sum() if 'posting_id' in df.columns else 0
    null_titles = df['job_title'].isnull().sum() if 'job_title' in df.columns else 0
    null_companies = df['company_name'].isnull().sum() if 'company_name' in df.columns else 0
    invalid_salaries = ((df['salary_min'] < 0) | (df['salary_max'] < 0)).sum() if {'salary_min','salary_max'}.issubset(df.columns) else 0
    invalid_dates = 0

    # basic foreign key checks placeholder (to be run after load)
    report = {
        'rows_processed': int(rows),
        'duplicates_removed': int(duplicates),
        'null_titles': int(null_titles),
        'null_companies': int(null_companies),
        'invalid_salaries': int(invalid_salaries),
        'invalid_dates': int(invalid_dates),
    }
    score = 100.0
    # simple scoring deductions
    score -= duplicates * 0.01
    score -= (null_titles + null_companies) * 0.02
    score -= invalid_salaries * 0.05
    report['quality_score'] = max(0.0, round(score, 2))
    return report


def save_report(report: Dict, path: str = 'docs/reports/quality_report.json'):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf8') as f:
        json.dump(report, f, indent=2)
    LOGGER.info("Saved quality report to %s", p)
