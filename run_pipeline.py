"""Run the full pipeline end-to-end.

Usage: python run_pipeline.py

Steps executed:
 - scripts/create_views.py
 - scripts/run_load.py
 - scripts/create_views.py (ensure staging table refreshed)
 - scripts/generate_reports.py
 - package release into releases/YYYY-MM-DD/

Exits with non-zero if the data-quality gate fails.
"""
from pathlib import Path
import subprocess
import sys
import json
import shutil
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run_cmd(args, desc):
    print(f'--> {desc}')
    r = subprocess.run([PY] + args, cwd=ROOT)
    if r.returncode != 0:
        print(f'[ERROR] Step failed: {desc} (exit {r.returncode})')
        sys.exit(r.returncode)
    print(f'[OK] {desc}')


def read_insights_latest():
    latest = ROOT / 'reports' / 'latest' / 'insights_summary.json'
    if not latest.exists():
        return None
    return json.loads(latest.read_text(encoding='utf-8'))


def package_release():
    ts = datetime.utcnow().strftime('%Y-%m-%d')
    out = ROOT / 'releases' / ts
    out.mkdir(parents=True, exist_ok=True)
    # copy report + insights from reports/latest
    src_md = ROOT / 'reports' / 'latest' / 'weekly_report.md'
    src_json = ROOT / 'reports' / 'latest' / 'insights_summary.json'
    if src_md.exists():
        shutil.copy(src_md, out / 'weekly_report.md')
    if src_json.exists():
        shutil.copy(src_json, out / 'insights_summary.json')

    # copy screenshots if present
    screenshots = ROOT / 'docs' / 'releases' / 'latest' / 'screenshots'
    for name in ['top_skills.png', 'city_distribution.png', 'top_companies.png']:
        src_img = screenshots / name
        if src_img.exists():
            shutil.copy(src_img, out / name)

    # schema snapshot
    db = ROOT / 'data' / 'warehouse' / 'jobpulse.db'
    if db.exists():
        snap = {}
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(f"PRAGMA table_info('{t}')")
            cols = [{'cid': r[0], 'name': r[1], 'type': r[2], 'notnull': r[3], 'dflt_value': r[4], 'pk': r[5]} for r in cur.fetchall()]
            snap[t] = cols
        conn.close()
        (out / 'schema_snapshot.json').write_text(json.dumps(snap, indent=2), encoding='utf-8')

    print('[OK] Packaged release to', out)


def main():
    # 1. create views (loads staging table)
    run_cmd(['scripts/create_views.py'], 'Create views / load staging table')

    # 2. run load (populates warehouse fact/dim)
    run_cmd(['scripts/run_load.py'], 'Run load into warehouse')

    # 3. refresh views (ensure staging reflects current data)
    run_cmd(['scripts/create_views.py'], 'Refresh views')

    # 4. generate reports
    run_cmd(['scripts/generate_reports.py'], 'Generate reports')

    # inspect DQ
    insights = read_insights_latest()
    if insights is None:
        print('[ERROR] insights_summary.json not found in reports/latest')
        sys.exit(3)
    dq = insights.get('data_quality', {})
    passed = dq.get('passed', False)

    # print concise pipeline summary
    print('--- Pipeline summary ---')
    print('[OK] Load complete')
    print('[OK] Views refreshed')
    print('[OK] Reports generated')
    if passed:
        print('[OK] DQ Gate Passed')
    else:
        print('[FAIL] DQ Gate Failed')
        print('Reasons:')
        for r in dq.get('reasons', []):
            print(' -', r)

    # package release (even if DQ fails, still snapshot)
    package_release()

    if not passed:
        sys.exit(2)


if __name__ == '__main__':
    main()
