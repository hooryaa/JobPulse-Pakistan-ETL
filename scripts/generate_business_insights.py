"""Generate business insights, analytics-ready CSVs, charts, and markdown reports
from the demo SQLite warehouse at data/warehouse/demo.db.

Outputs:
- docs/business_insights.md
- docs/demo/* (summary files and charts)
- docs/diagrams/*.mmd (Mermaid diagrams)
- powerbi_*.csv
"""
from pathlib import Path
import sqlite3
import pandas as pd
import json
import math
import re
import unicodedata

try:
    import matplotlib.pyplot as plt
    _HAS_MATPLOTLIB = True
except Exception:
    _HAS_MATPLOTLIB = False

try:
    import ftfy
    _HAS_FTFY = True
except Exception:
    _HAS_FTFY = False


DB_PATH = Path('data/warehouse/demo.db')
# Use release-style output folders so each run creates a fresh artifact set
OUT_DIR = Path('docs/releases/2026-06-23')
DIAG_DIR = Path('docs/diagrams')
OUT_DIR.mkdir(parents=True, exist_ok=True)
DIAG_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_chart_label(text: str) -> str:
    """Sanitize a label for chart rendering.

    Rules:
    - max length 40 characters (truncate)
    - remove control characters
    - attempt to fix mojibake using ftfy when available
    - only allow printable ASCII characters (fallback to 'Unknown')
    - return 'Unknown' for empty/invalid results
    """
    if text is None:
        return 'Unknown'
    try:
        s = str(text)
    except Exception:
        return 'Unknown'

    # normalize to NFC/NFKC
    try:
        s = unicodedata.normalize('NFKC', s)
    except Exception:
        pass

    # attempt to fix mojibake / encoding issues if ftfy available
    if _HAS_FTFY:
        try:
            fixed = ftfy.fix_text(s)
            if fixed and fixed.strip():
                s = fixed
        except Exception:
            pass

    # remove control chars
    s = re.sub(r'[\x00-\x1F\x7F]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()

    # limit length
    if len(s) > 40:
        s = s[:37].rstrip() + '...'

    # require printable ASCII only to avoid font glyph warnings
    if not s:
        return 'Unknown'
    if all((ord(ch) < 128 and ch.isprintable()) for ch in s):
        return s

    return 'Unknown'


def to_native(val):
    # convert numpy and other types to native Python
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if hasattr(val, 'item'):
        return val.item()
    if isinstance(val, (float, int, str, bool)) or val is None:
        return val
    try:
        return float(val)
    except Exception:
        return str(val)


def read_df(sql):
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def save_powerbi_csvs():
    # jobs
    df = read_df('SELECT fp.posting_key, fp.posting_id, dj.job_title, dc.company_name, dl.city, dl.remote_type, fp.salary_min, fp.salary_max, fp.salary_avg FROM fact_job_postings fp LEFT JOIN dim_job dj ON fp.job_key = dj.job_key LEFT JOIN dim_company dc ON fp.company_key = dc.company_key LEFT JOIN dim_location dl ON fp.location_key = dl.location_key')
    df.to_csv('powerbi_jobs.csv', index=False)
    # skills
    df_sk = read_df('SELECT fjs.posting_key, ds.skill_name FROM fact_job_skills fjs JOIN dim_skill ds ON fjs.skill_key = ds.skill_key')
    df_sk.to_csv('powerbi_skills.csv', index=False)
    # companies
    df_co = read_df('SELECT * FROM dim_company')
    df_co.to_csv('powerbi_companies.csv', index=False)
    # locations
    # include normalized_location for Power BI
    df_loc = read_df('SELECT location_key, city, state, country, normalized_location, remote_type FROM dim_location')
    df_loc.to_csv('powerbi_locations.csv', index=False)
    # trends dataset (skill demand snapshot)
    df_trends = read_df('SELECT ds.skill_name AS skill, COUNT(*) AS job_count FROM dim_skill ds JOIN fact_job_skills fjs ON ds.skill_key = fjs.skill_key GROUP BY ds.skill_name ORDER BY job_count DESC')
    try:
        total_jobs = read_df('SELECT COUNT(*) AS cnt FROM fact_job_postings').iloc[0,0]
        if total_jobs and total_jobs > 0:
            df_trends['pct_of_jobs'] = (df_trends['job_count'] / float(total_jobs) * 100.0).round(2)
        else:
            df_trends['pct_of_jobs'] = None
    except Exception:
        df_trends['pct_of_jobs'] = None
    df_trends.to_csv('powerbi_trends.csv', index=False)
    # remote analysis
    df_remote = read_df('SELECT dl.remote_type, COUNT(*) AS cnt FROM fact_job_postings fp JOIN dim_location dl ON fp.location_key = dl.location_key GROUP BY dl.remote_type')
    df_remote.to_csv('powerbi_remote_analysis.csv', index=False)


def generate_charts(insights):
    if not _HAS_MATPLOTLIB:
        print('matplotlib not available; skipping PNG generation')
        return
    chart_stats = {
        'removed_labels': [],
        'repaired_labels': [],
        'replaced_with_unknown': [],
        'total_labels_processed': 0,
    }
    # top skills
    top_sk = read_df('SELECT ds.skill_name, COUNT(*) AS cnt FROM dim_skill ds JOIN fact_job_skills fjs ON ds.skill_key = fjs.skill_key GROUP BY ds.skill_name ORDER BY cnt DESC LIMIT 20')
    if not top_sk.empty:
        names = []
        counts = []
        for name, cnt in zip(top_sk['skill_name'], top_sk['cnt']):
            chart_stats['total_labels_processed'] += 1
            clean = sanitize_chart_label(name)
            if clean == 'Unknown':
                chart_stats['replaced_with_unknown'].append(name)
                continue
            if clean != name:
                chart_stats['repaired_labels'].append((name, clean))
            names.append(clean)
            counts.append(cnt)
        if names:
            plt.figure(figsize=(10,6))
            plt.bar(names, counts)
            plt.xticks(rotation=45, ha='right')
            plt.title('Top 20 Skills')
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'top_skills.png')
            plt.close()

    # Technology demand (similar to top skills but styled for presentation)
    if not top_sk.empty:
        names = []
        counts = []
        for name, cnt in zip(top_sk['skill_name'], top_sk['cnt']):
            clean = sanitize_chart_label(name)
            if clean == 'Unknown':
                chart_stats['replaced_with_unknown'].append(name)
                continue
            names.append(clean)
            counts.append(cnt)
        if names:
            plt.figure(figsize=(10,6))
            plt.barh(names[::-1], counts[::-1], color='#2a9d8f')
            plt.xlabel('Number of Postings')
            plt.title('Technology Demand (Top Skills)')
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'technology_demand.png')
            plt.close()

    # remote distribution
    remote = read_df('SELECT COALESCE(dl.remote_type, "unknown") AS remote_type, COUNT(*) AS cnt FROM fact_job_postings fp JOIN dim_location dl ON fp.location_key = dl.location_key GROUP BY remote_type')
    if not remote.empty:
        plt.figure(figsize=(6,4))
        plt.pie(remote['cnt'], labels=remote['remote_type'], autopct='%1.1f%%')
        plt.title('Remote vs Hybrid vs On-site')
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'remote_distribution.png')
        plt.close()

    # top companies (exclude corrupted labels)
    top_co = read_df('SELECT dc.company_name, COUNT(*) AS cnt FROM fact_job_postings fp JOIN dim_company dc ON fp.company_key = dc.company_key GROUP BY dc.company_name ORDER BY cnt DESC LIMIT 20')
    if not top_co.empty:
        names = []
        counts = []
        for name, cnt in zip(top_co['company_name'], top_co['cnt']):
            chart_stats['total_labels_processed'] += 1
            clean = sanitize_chart_label(name)
            if clean == 'Unknown':
                chart_stats['removed_labels'].append(name)
                chart_stats['replaced_with_unknown'].append(name)
                continue
            if clean != name:
                chart_stats['repaired_labels'].append((name, clean))
            names.append(clean)
            counts.append(cnt)
        if names:
            plt.figure(figsize=(10,6))
            plt.bar(names, counts)
            plt.xticks(rotation=45, ha='right')
            plt.title('Top Hiring Companies')
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'top_companies.png')
            plt.close()

    # job categories / titles (exclude corrupted labels)
    job_cat = read_df('SELECT job_title, COUNT(*) AS cnt FROM fact_job_postings fp JOIN dim_job dj ON fp.job_key = dj.job_key GROUP BY job_title ORDER BY cnt DESC LIMIT 20')
    if not job_cat.empty:
        names = []
        counts = []
        for name, cnt in zip(job_cat['job_title'], job_cat['cnt']):
            chart_stats['total_labels_processed'] += 1
            clean = sanitize_chart_label(name)
            if clean == 'Unknown':
                chart_stats['removed_labels'].append(name)
                chart_stats['replaced_with_unknown'].append(name)
                continue
            if clean != name:
                chart_stats['repaired_labels'].append((name, clean))
            names.append(clean)
            counts.append(cnt)
        if names:
            plt.figure(figsize=(10,6))
            plt.bar(names, counts)
            plt.xticks(rotation=45, ha='right')
            plt.title('Top Job Titles')
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'job_categories.png')
            plt.close()

    # top locations (exclude corrupted labels)
    loc = read_df('SELECT dl.city, dl.country, COUNT(*) AS cnt FROM fact_job_postings fp JOIN dim_location dl ON fp.location_key = dl.location_key GROUP BY dl.city, dl.country ORDER BY cnt DESC LIMIT 20')
    if not loc.empty:
        names = []
        counts = []
        for city, country, cnt in zip(loc['city'].fillna('Unknown'), loc['country'].fillna(''), loc['cnt']):
            full = city if city and city != 'Unknown' else (country or 'Unknown')
            chart_stats['total_labels_processed'] += 1
            clean = sanitize_chart_label(full)
            if clean == 'Unknown':
                chart_stats['removed_labels'].append(full)
                chart_stats['replaced_with_unknown'].append(full)
                continue
            if clean != full:
                chart_stats['repaired_labels'].append((full, clean))
            names.append(clean)
            counts.append(cnt)
        if names:
            plt.figure(figsize=(10,6))
            plt.bar(names, counts)
            plt.xticks(rotation=45, ha='right')
            plt.title('Top Hiring Cities')
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'top_locations.png')
            plt.close()

    # salary insights chart only if sufficient coverage
    sal = read_df('SELECT salary_avg FROM fact_job_postings')
    non_null = sal['salary_avg'].notna().sum()
    total = len(sal)
    coverage = (non_null / total * 100.0) if total else 0.0
    insights['salary_data_coverage'] = round(coverage, 2)
    if coverage >= 20.0 and non_null > 5:
        plt.figure(figsize=(8,4))
        sal['salary_avg'].dropna().astype(float).hist(bins=30)
        plt.title('Salary Distribution')
        plt.xlabel('Avg Salary')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'salary_distribution.png')
        plt.close()
        insights['salary_visualization_generated'] = True
    else:
        insights['salary_visualization_generated'] = False
        insights['salary_visualization_reason'] = 'Insufficient salary data'

        # write chart generation report
        report_lines = []
        report_lines.append('# Chart Generation Report')
        report_lines.append('')
        report_lines.append(f"- Total labels processed: {chart_stats['total_labels_processed']}")
        report_lines.append(f"- Labels removed (excluded from charts): {len(chart_stats['removed_labels'])}")
        report_lines.append(f"- Labels repaired: {len(chart_stats['repaired_labels'])}")
        report_lines.append(f"- Labels replaced with 'Unknown': {len(chart_stats['replaced_with_unknown'])}")
        report_lines.append('')
        if chart_stats['removed_labels']:
            report_lines.append('## Removed Labels (sample)')
            for v in chart_stats['removed_labels'][:50]:
                report_lines.append(f'- {v}')
            report_lines.append('')
        if chart_stats['repaired_labels']:
            report_lines.append('## Repaired Labels (original -> repaired)')
            for orig, rep in chart_stats['repaired_labels'][:200]:
                report_lines.append(f'- {orig} -> {rep}')
            report_lines.append('')
        if chart_stats['replaced_with_unknown']:
            report_lines.append('## Replaced with Unknown (sample)')
            for v in chart_stats['replaced_with_unknown'][:50]:
                report_lines.append(f'- {v}')
            report_lines.append('')

        with open(OUT_DIR / 'chart_generation_report.md', 'w', encoding='utf8') as f:
            f.write('\n'.join(report_lines))


def build_insights():
    """Build comprehensive business insights from warehouse data.
    
    Quality Rules:
    - Skip salary analytics if coverage < 20%
    - Only include valid data in aggregations
    - Report data quality metrics
    """
    insights = {}
    
    # Total counts
    total_jobs = read_df('SELECT COUNT(*) AS cnt FROM fact_job_postings').iloc[0, 0]
    total_companies = read_df('SELECT COUNT(*) AS cnt FROM dim_company').iloc[0, 0]
    total_skills = read_df('SELECT COUNT(*) AS cnt FROM dim_skill').iloc[0, 0]
    total_locations = read_df('SELECT COUNT(*) AS cnt FROM dim_location').iloc[0, 0]
    
    insights.update({
        'total_jobs_analyzed': int(total_jobs),
        'total_companies': int(total_companies),
        'total_skills': int(total_skills),
        'total_locations': int(total_locations),
    })
    
    # ===== DATA QUALITY METRICS =====
    
    # Salary data quality
    salary_df = read_df(
        'SELECT salary_avg FROM fact_job_postings WHERE salary_avg IS NOT NULL AND salary_avg > 0'
    )
    salary_non_null = len(salary_df)
    salary_coverage = (salary_non_null / total_jobs * 100.0) if total_jobs > 0 else 0.0
    insights['salary_data_coverage_pct'] = round(salary_coverage, 2)
    insights['salary_records_with_data'] = int(salary_non_null)
    
    # Location data quality
    location_df = read_df(
        "SELECT COUNT(*) AS cnt FROM dim_location WHERE COALESCE(city, '') NOT IN ('', 'Unknown')"
    )
    valid_locations = location_df.iloc[0, 0]
    location_coverage = (valid_locations / total_locations * 100.0) if total_locations > 0 else 0.0
    insights['location_coverage_pct'] = round(location_coverage, 2)
    
    # Skill extraction quality
    skill_df = read_df('SELECT COUNT(*) AS cnt FROM fact_job_skills')
    skill_associations = skill_df.iloc[0, 0]
    skills_per_job = (skill_associations / total_jobs) if total_jobs > 0 else 0
    insights['avg_skills_per_job'] = round(skills_per_job, 2)
    insights['total_skill_associations'] = int(skill_associations)
    
    # ===== TOP SKILLS =====
    top_sk = read_df(
        'SELECT ds.skill_name, COUNT(*) AS cnt FROM dim_skill ds '
        'JOIN fact_job_skills fjs ON ds.skill_key = fjs.skill_key '
        'GROUP BY ds.skill_name ORDER BY cnt DESC LIMIT 20'
    )
    insights['top_skills'] = [
        {'skill': r[0], 'count': int(r[1]), 'pct': round(100.0 * r[1] / total_jobs, 1)}
        for r in top_sk.values
    ]
    
    # ===== REMOTE DISTRIBUTION =====
    remote = read_df(
        'SELECT COALESCE(dl.remote_type, "Unknown") AS remote_type, COUNT(*) AS cnt '
        'FROM fact_job_postings fp '
        'JOIN dim_location dl ON fp.location_key = dl.location_key '
        'GROUP BY remote_type ORDER BY cnt DESC'
    )
    insights['remote_distribution'] = [
        {'remote_type': r[0], 'count': int(r[1]), 'pct': round(100.0 * r[1] / total_jobs, 1)}
        for r in remote.values
    ]
    
    # ===== TOP JOB TITLES =====
    top_titles = read_df(
        'SELECT dj.job_title, COUNT(*) AS cnt FROM fact_job_postings fp '
        'JOIN dim_job dj ON fp.job_key = dj.job_key '
        'GROUP BY dj.job_title ORDER BY cnt DESC LIMIT 20'
    )
    insights['top_job_titles'] = [
        {'title': r[0], 'count': int(r[1]), 'pct': round(100.0 * r[1] / total_jobs, 1)}
        for r in top_titles.values
    ]
    
    # ===== TOP COMPANIES =====
    top_co = read_df(
        'SELECT dc.company_name, COUNT(*) AS cnt FROM fact_job_postings fp '
        'JOIN dim_company dc ON fp.company_key = dc.company_key '
        'GROUP BY dc.company_name ORDER BY cnt DESC LIMIT 20'
    )
    insights['top_companies'] = [
        {'company': r[0], 'count': int(r[1])}
        for r in top_co.values
    ]
    
    # ===== TOP LOCATIONS =====
    top_loc = read_df(
        'SELECT COALESCE(dl.city, "Unknown") AS city, COUNT(*) AS cnt FROM fact_job_postings fp '
        'JOIN dim_location dl ON fp.location_key = dl.location_key '
        'GROUP BY city ORDER BY cnt DESC LIMIT 20'
    )
    insights['top_locations'] = [
        {'city': r[0], 'count': int(r[1])}
        for r in top_loc.values
    ]
    
    # ===== TOP REMOTE EMPLOYERS =====
    remote_co = read_df(
        "SELECT dc.company_name, COUNT(*) AS cnt FROM fact_job_postings fp "
        "JOIN dim_company dc ON fp.company_key = dc.company_key "
        "JOIN dim_location dl ON fp.location_key = dl.location_key "
        "WHERE dl.remote_type IN ('Remote', 'Hybrid') "
        "GROUP BY dc.company_name ORDER BY cnt DESC LIMIT 15"
    )
    insights['top_remote_employers'] = [
        {'company': r[0], 'count': int(r[1])}
        for r in remote_co.values
    ]
    
    # ===== TECHNOLOGY DEMAND RANKING =====
    # Calculate demand scores: count + percentage of jobs
    tech_demand = []
    for skill in insights['top_skills'][:15]:
        tech_demand.append({
            'rank': len(tech_demand) + 1,
            'skill': skill['skill'],
            'demand_level': 'Critical' if skill['pct'] > 30 else ('High' if skill['pct'] > 15 else 'Medium'),
            'job_count': skill['count'],
            'job_coverage_pct': skill['pct'],
        })
    insights['technology_demand'] = tech_demand
    
    # ===== JUNIOR SKILLS (for entry-level analysis) =====
    junior = read_df(
        "SELECT ds.skill_name, COUNT(*) AS cnt FROM fact_job_postings fp "
        "JOIN dim_job dj ON fp.job_key = dj.job_key "
        "JOIN fact_job_skills fjs ON fp.posting_key = fjs.posting_key "
        "JOIN dim_skill ds ON fjs.skill_key = ds.skill_key "
        "WHERE LOWER(COALESCE(dj.seniority_level, '')) LIKE '%junior%' "
        "   OR LOWER(COALESCE(dj.seniority_level, '')) LIKE '%entry%' "
        "GROUP BY ds.skill_name ORDER BY cnt DESC LIMIT 20"
    )
    insights['junior_skills'] = [
        {'skill': r[0], 'count': int(r[1])}
        for r in junior.values
    ]
    
    # ===== SALARY INSIGHTS (only if sufficient coverage) =====
    if salary_coverage >= 20.0 and salary_non_null > 5:
        sal_stats = read_df(
            'SELECT '
            'COUNT(*) AS count_non_null, '
            'MIN(salary_avg) AS min, '
            'MAX(salary_avg) AS max, '
            'AVG(salary_avg) AS mean, '
            'CAST((SELECT salary_avg FROM fact_job_postings WHERE salary_avg IS NOT NULL '
            'ORDER BY salary_avg LIMIT 1 OFFSET (COUNT(*)-1)/2) AS FLOAT) AS median '
            'FROM fact_job_postings WHERE salary_avg IS NOT NULL AND salary_avg > 0'
        )
        row = sal_stats.iloc[0]
        insights['salary_summary'] = {
            'count_non_null': int(to_native(row['count_non_null'])),
            'min': float(to_native(row['min'])),
            'max': float(to_native(row['max'])),
            'mean': float(to_native(row['mean'])),
            'median': float(to_native(row['median'])),
            'data_quality': 'Good (≥20% coverage)',
        }
    else:
        insights['salary_summary'] = {
            'count_non_null': int(salary_non_null),
            'data_quality': f'Insufficient data ({salary_coverage:.1f}% coverage) - salary analysis skipped',
            'note': 'Salary data is too sparse to generate reliable insights (< 20% coverage).',
        }
    
    return insights


def write_markdown(insights):
    md = []
    md.append('# Business Insights — JobPulse Demo')
    md.append('')
    md.append('## Executive Summary')
    md.append(f"- **Total jobs analyzed:** {insights['total_jobs_analyzed']}")
    md.append(f"- **Total companies:** {insights['total_companies']}")
    md.append(f"- **Total skills extracted:** {insights['total_skills']}")
    md.append(f"- **Total locations:** {insights['total_locations']}")
    md.append('')
    md.append('### Data Quality Metrics')
    md.append(f"- **Skill extraction quality:** {insights['avg_skills_per_job']} avg skills per job ({insights['total_skill_associations']} total associations)")
    md.append(f"- **Location data coverage:** {insights['location_coverage_pct']}%")
    md.append(f"- **Salary data coverage:** {insights['salary_data_coverage_pct']}%")
    if insights['salary_data_coverage_pct'] < 20:
        md.append('  - ⚠️ Salary coverage is below 20%; salary analysis skipped to avoid misleading insights')
    md.append('')
    
    # Remote distribution
    md.append('## Work Type Distribution')
    for item in insights['remote_distribution']:
        md.append(f"- **{item['remote_type']}**: {item['count']} postings ({item['pct']}%)")
    md.append('')
    
    # Top job titles
    md.append('## Top Job Titles (Top 10)')
    for i, item in enumerate(insights['top_job_titles'][:10], 1):
        md.append(f"{i}. **{item['title']}** — {item['count']} postings ({item['pct']}%)")
    md.append('')
    
    # Technology demand
    md.append('## Technology Demand Rankings')
    md.append('Ranked by job coverage and market presence:')
    md.append('')
    for item in insights['technology_demand']:
        md.append(f"{item['rank']}. **{item['skill']}** — {item['demand_level']} demand")
        md.append(f"   - Found in {item['job_count']} postings ({item['job_coverage_pct']}% of all jobs)")
    md.append('')
    
    # Top skills
    md.append('## Top Skills (Top 15)')
    for i, item in enumerate(insights['top_skills'][:15], 1):
        md.append(f"{i}. **{item['skill']}** — {item['count']} postings ({item['pct']}%)")
    md.append('')
    
    # Top remote-friendly employers
    if insights['top_remote_employers']:
        md.append('## Top Remote-Friendly Employers')
        md.append('Companies with most remote or hybrid positions:')
        md.append('')
        for i, item in enumerate(insights['top_remote_employers'][:10], 1):
            md.append(f"{i}. **{item['company']}** — {item['count']} remote/hybrid roles")
        md.append('')
    
    # Top locations
    md.append('## Top Hiring Locations (Top 10)')
    for i, item in enumerate(insights['top_locations'][:10], 1):
        md.append(f"{i}. **{item['city']}** — {item['count']} postings")
    md.append('')
    
    # Top companies
    md.append('## Top Hiring Companies (Top 10)')
    for i, item in enumerate(insights['top_companies'][:10], 1):
        md.append(f"{i}. **{item['company']}** — {item['count']} postings")
    md.append('')
    
    # Junior skills
    if insights['junior_skills']:
        md.append('## Entry-Level Skills')
        md.append('Most sought skills for junior/entry-level positions:')
        md.append('')
        for item in insights['junior_skills'][:10]:
            md.append(f"- **{item['skill']}** — {item['count']} postings")
        md.append('')
    
    # Salary insights
    md.append('## Salary Insights')
    sal = insights['salary_summary']
    if 'min' in sal and sal['min'] is not None:
        md.append(f"- **Data Quality:** {sal.get('data_quality', 'Good')}")
        md.append(f"- **Records with salary data:** {sal['count_non_null']}")
        md.append(f"- **Salary Range:** ${sal['min']:,.0f} - ${sal['max']:,.0f}")
        md.append(f"- **Median Salary:** ${sal['median']:,.0f}")
        md.append(f"- **Average Salary:** ${sal['mean']:,.0f}")
    else:
        md.append(f"- **Data Quality:** {sal.get('data_quality', 'Insufficient')}")
        if 'note' in sal:
            md.append(f"- {sal['note']}")
    md.append('')
    
    md.append('## Key Findings')
    md.append('')
    
    # Calculate key metrics
    total_jobs = insights['total_jobs_analyzed']
    
    # Top technologies
    if insights['top_skills']:
        top_skill = insights['top_skills'][0]
        md.append(f"- **Most in-demand technology:** {top_skill['skill']} ({top_skill['pct']}% of postings)")
    
    # Remote work prevalence
    remote_dist = {item['remote_type']: item for item in insights['remote_distribution']}
    remote_pct = sum(item['pct'] for key, item in remote_dist.items() if key.lower() == 'remote')
    hybrid_pct = sum(item['pct'] for key, item in remote_dist.items() if key.lower() == 'hybrid')
    md.append(f"- **Remote/hybrid prevalence:** {remote_pct + hybrid_pct:.1f}% of opportunities offer flexibility")
    
    # Skill coverage
    if insights['avg_skills_per_job'] > 0:
        md.append(f"- **Average skills per posting:** {insights['avg_skills_per_job']:.1f} technologies mentioned")
    
    # Company diversity
    unique_companies = insights['total_companies']
    if unique_companies > 0:
        concentration = (insights['top_companies'][0]['count'] / total_jobs * 100) if insights['top_companies'] else 0
        md.append(f"- **Company diversity:** {unique_companies} unique companies, top company has {concentration:.1f}% of postings")

    Path('docs').mkdir(parents=True, exist_ok=True)
    with open('docs/business_insights.md', 'w', encoding='utf8') as f:
        f.write('\n'.join(md))



def save_json_reports():
    # copy existing pipeline/quality reports into docs/demo if present, converting numpy types
    def load_and_normalize(src):
        p = Path(src)
        if not p.exists():
            return None
        obj = json.loads(p.read_text(encoding='utf8'))
        # convert numeric numpy types
        def norm(o):
            if isinstance(o, dict):
                return {k: norm(v) for k,v in o.items()}
            if isinstance(o, list):
                return [norm(x) for x in o]
            try:
                if hasattr(o, 'item'):
                    return o.item()
            except Exception:
                pass
            if isinstance(o, float) and (math.isfinite(o) == False):
                return None
            return o
        return norm(obj)

    p1 = load_and_normalize('logs/pipeline_summary.json')
    if p1 is not None:
        with open(OUT_DIR / 'pipeline_summary.json', 'w', encoding='utf8') as f:
            json.dump(p1, f, indent=2)

    p2 = load_and_normalize('docs/reports/quality_report.json')
    if p2 is not None:
        with open(OUT_DIR / 'quality_report.json', 'w', encoding='utf8') as f:
            json.dump(p2, f, indent=2)


def write_demo_summaries(insights):
    # pipeline execution summary
    with open(OUT_DIR / 'pipeline_execution.md', 'w', encoding='utf8') as f:
        f.write('# Pipeline Execution\n')
        f.write('The demo pipeline ingested and transformed data into the demo warehouse.\n')
        f.write(f"- Total jobs analyzed: {insights['total_jobs_analyzed']}\n")

    # data quality summary
    with open(OUT_DIR / 'data_quality_summary.md', 'w', encoding='utf8') as f:
        f.write('# Data Quality Summary\n')
        f.write('See docs/demo/quality_report.json for full details. Key points:\n')
        qr = OUT_DIR / 'quality_report.json'
        if qr.exists():
            f.write(qr.read_text(encoding='utf8'))
        else:
            f.write('- Quality report not available.\n')

    # business insights short summary
    with open(OUT_DIR / 'business_insights_summary.md', 'w', encoding='utf8') as f:
        f.write('# Business Insights Summary\n')
        f.write('A short summary of key metrics for recruiter review.\n')
        f.write(f"- Total jobs: {insights['total_jobs_analyzed']}\n")
        f.write(f"- Top skill: {insights['top_skills'][0]['skill'] if insights['top_skills'] else 'n/a'}\n")


def write_mermaid_diagrams():
    etl = '''
graph TD
  A[RemoteOK API] --> B[Raw JSON]
  B --> C[Staging (parquet/csv)]
  C --> D[Transform: normalize, extract skills]
  D --> E[Warehouse (Postgres/SQLite)]
  E --> F[Analytics & Power BI]
'''
    (DIAG_DIR / 'etl_architecture.mmd').write_text(etl, encoding='utf8')

    star = '''
flowchart LR
  subgraph Dimensions
    DC[dim_company]
    DJ[dim_job]
    DL[dim_location]
    DS[dim_skill]
    DD[dim_date]
  end
  FP[fact_job_postings]
  FS[fact_job_skills]
  DC --> FP
  DJ --> FP
  DL --> FP
  DD --> FP
  FP --> FS
  DS --> FS
'''
    (DIAG_DIR / 'star_schema.mmd').write_text(star, encoding='utf8')

    flow = '''
sequenceDiagram
    participant U as User
    participant S as Scheduler
    participant P as Pipeline
    participant W as Warehouse
    U->>S: Trigger
    S->>P: Run extract->transform->load
    P->>W: Upsert dims & facts
    W->>U: Provide CSVs/insights
'''
    (DIAG_DIR / 'data_flow.mmd').write_text(flow, encoding='utf8')


def main():
    if not DB_PATH.exists():
        print('Demo DB not found. Run scripts/demo_run.py first.')
        return
    insights = build_insights()
    save_powerbi_csvs()
    # generate charts (if possible) and collect salary coverage info
    generate_charts(insights)
    write_markdown(insights)
    save_json_reports()
    write_demo_summaries(insights)
    write_mermaid_diagrams()
    # warehouse summary CSV
    try:
        df = read_df('SELECT * FROM fact_job_postings LIMIT 1000')
        df.to_csv(OUT_DIR / 'warehouse_summary.csv', index=False)
    except Exception:
        pass
    print('Business insights and demo artifacts generated in docs/ and docs/demo/')


if __name__ == '__main__':
    main()
