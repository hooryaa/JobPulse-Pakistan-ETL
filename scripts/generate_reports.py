"""Generate analytics reports from warehouse and staging data.

Outputs:
 - reports/weekly_report.md
 - reports/insights_summary.json

Prefer warehouse for skill metrics; fall back to staging for city/company and salary stats.
"""
from pathlib import Path
import json
from datetime import datetime
import sqlite3

DB_PATH = 'data/warehouse/jobpulse.db'

# Metrics contract
METRICS = {
    'top_skills': 'vw_top_skills',
    'city_demand': 'vw_city_demand',
    'company_activity': 'vw_company_activity',
}


def query_view(view_name, limit=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sql = f"SELECT * FROM {view_name}"
    if limit:
        sql = sql + f" LIMIT {limit}"
    try:
        cur.execute(sql)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def salary_stats_from_staging_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staging_job_postings'")
    if not cur.fetchone():
        conn.close()
        return {}
    # inspect available columns
    cur.execute("PRAGMA table_info('staging_job_postings')")
    cols_info = cur.fetchall()
    cols = [c[1] for c in cols_info]
    vals = []
    if 'salary_avg' in cols:
        cur.execute("SELECT salary_avg FROM staging_job_postings")
        for (sa,) in cur.fetchall():
            try:
                if sa is not None:
                    vals.append(float(sa))
            except Exception:
                continue
    elif 'salary_min' in cols and 'salary_max' in cols:
        cur.execute("SELECT salary_min, salary_max FROM staging_job_postings")
        for smin, smax in cur.fetchall():
            try:
                if smin is not None and smax is not None:
                    vals.append((float(smin) + float(smax)) / 2.0)
            except Exception:
                continue
    conn.close()
    if not vals:
        return {}
    import statistics
    return {
        'count': len(vals),
        'mean': statistics.mean(vals),
        'median': statistics.median(vals),
        'min': min(vals),
        'max': max(vals),
    }


def data_quality_check(min_postings=50, min_skill_coverage_pct=30.0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    snapshot = {}
    reasons = []
    # total postings
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staging_job_postings'")
    if not cur.fetchone():
        conn.close()
        snapshot = {'total_postings': 0, 'postings_with_skills': 0, 'skill_coverage_pct': 0.0, 'top_skill': None}
        reasons.append('staging_job_postings table missing')
        return False, {**snapshot, 'reasons': reasons, 'passed': False}

    cur.execute('SELECT COUNT(*) FROM staging_job_postings')
    total_postings = cur.fetchone()[0] or 0
    # postings with skills
    cur.execute("SELECT COUNT(DISTINCT posting_key) FROM fact_job_skills")
    row = cur.fetchone()
    postings_with_skills = row[0] if row is not None else 0
    skill_cov = (postings_with_skills / total_postings * 100.0) if total_postings else 0.0

    # top skill
    cur.execute("SELECT skill FROM vw_top_skills LIMIT 1")
    r = cur.fetchone()
    top_skill = r[0] if r else None

    # city coverage
    cur.execute("SELECT COUNT(DISTINCT city) FROM staging_job_postings")
    city_count = cur.fetchone()[0] or 0

    if total_postings < min_postings:
        reasons.append(f'total_postings {total_postings} < min_postings {min_postings}')
    if skill_cov < min_skill_coverage_pct:
        reasons.append(f'skill_coverage_pct {skill_cov:.1f}% < min {min_skill_coverage_pct}%')
    if not top_skill:
        reasons.append('no top skill found')
    if city_count == 0:
        reasons.append('no cities present in staging')

    snapshot = {
        'total_postings': int(total_postings),
        'postings_with_skills': int(postings_with_skills),
        'skill_coverage_pct': float(skill_cov),
        'top_skill': top_skill,
    }
    conn.close()
    passed = len(reasons) == 0
    return passed, {**snapshot, 'reasons': reasons, 'passed': passed}


def write_markdown(report_path: Path, insights: dict):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"# Weekly JobPulse Report — {datetime.utcnow().date()}")
    # Data quality snapshot
    dq = insights.get('data_quality', {})
    lines.append("")
    lines.append("## DATA QUALITY SNAPSHOT")
    if dq:
        lines.append(f"- total_postings: {dq.get('total_postings')}")
        lines.append(f"- postings_with_skills: {dq.get('postings_with_skills')}")
        lines.append(f"- skill_coverage_pct: {dq.get('skill_coverage_pct'):.1f}%")
        lines.append(f"- top_skill: {dq.get('top_skill')}")
        if not dq.get('passed'):
            lines.append("")
            lines.append("**DATA QUALITY GATE FAILED:**")
            for r in dq.get('reasons', []):
                lines.append(f"- {r}")
    else:
        lines.append("No data quality information available")
    lines.append("")
    lines.append("## Top Skills")
    for s in insights.get('top_skills', []):
        lines.append(f"- {s.get('skill')}: {s.get('count')}")
    lines.append("")
    lines.append("## Top Cities")
    for item in insights.get('city_demand', []):
        # view returns {city, job_count}
        lines.append(f"- {item.get('city')}: {item.get('job_count')}")
    lines.append("")
    lines.append("## Top Companies")
    for item in insights.get('company_activity', []):
        lines.append(f"- {item.get('company_name')}: {item.get('job_count')}")
    lines.append("")
    lines.append("## Salary Summary")
    sal = insights.get('salary_stats', {})
    if sal:
        lines.append(f"- Count: {sal['count']}")
        lines.append(f"- Mean: {sal['mean']:.2f}")
        lines.append(f"- Median: {sal['median']:.2f}")
        lines.append(f"- Min: {sal['min']:.2f}")
        lines.append(f"- Max: {sal['max']:.2f}")
    else:
        lines.append("No salary data available")

    report_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    # ensure DB exists
    if not Path(DB_PATH).exists():
        print('Warehouse DB not found at', DB_PATH)
        return
    # Ensure views exist (create_views.py should be run first)
    # Query metrics from views
    # Data quality checks
    dq_passed, dq_snapshot = data_quality_check()

    insights = {}
    insights['data_quality'] = dq_snapshot
    insights['top_skills'] = query_view(METRICS['top_skills'], limit=20)
    insights['city_demand'] = query_view(METRICS['city_demand'], limit=20)
    insights['company_activity'] = query_view(METRICS['company_activity'], limit=20)
    insights['salary_stats'] = salary_stats_from_staging_table()

    if not dq_passed:
        print('Data quality gate failed; writing snapshot report and aborting insights generation')

    # timestamped output
    ts = datetime.utcnow().strftime('%Y-%m-%d')
    out_dir = Path('reports') / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / 'weekly_report.md'
    json_path = out_dir / 'insights_summary.json'
    write_markdown(md_path, insights)
    json_path.write_text(json.dumps(insights, indent=2), encoding='utf-8')

    # also update latest/ for convenience
    latest_dir = Path('reports') / 'latest'
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_md = latest_dir / 'weekly_report.md'
    latest_json = latest_dir / 'insights_summary.json'
    latest_md.write_text(md_path.read_text(encoding='utf-8'), encoding='utf-8')
    latest_json.write_text(json_path.read_text(encoding='utf-8'), encoding='utf-8')

    print('Reports generated:', md_path, json_path)


if __name__ == '__main__':
    main()
