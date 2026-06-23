"""Generate CSV exports and simple PNG visuals from the demo warehouse.

Creates docs/demo/*.csv and docs/demo/*.png for README and portfolio screenshots.
"""
import os
from pathlib import Path
import sqlite3
import pandas as pd

# matplotlib is optional for PNG generation; allow CSV-only runs
try:
    import matplotlib.pyplot as plt
    _HAS_MATPLOTLIB = True
except Exception:
    _HAS_MATPLOTLIB = False


def query_df(conn, sql):
    return pd.read_sql_query(sql, conn)


def ensure_dirs():
    Path('docs/demo').mkdir(parents=True, exist_ok=True)


def export_tables(conn):
    ensure_dirs()
    tables = ['dim_company', 'dim_skill', 'dim_location', 'dim_job', 'fact_job_postings']
    for t in tables:
        try:
            df = query_df(conn, f'SELECT * FROM {t} LIMIT 1000')
            df.to_csv(f'docs/demo/{t}.csv', index=False)
        except Exception:
            # table might not exist
            pass


def make_quality_png(conn):
    ensure_dirs()
    try:
        if not _HAS_MATPLOTLIB:
            print('matplotlib not installed; skipping PNG generation for quality report')
            return
        df = query_df(conn, 'SELECT salary_avg FROM fact_job_postings WHERE salary_avg IS NOT NULL')
        if df.empty:
            return
        plt.figure(figsize=(6,4))
        df['salary_avg'].hist(bins=30)
        plt.title('Salary Distribution')
        plt.xlabel('Avg Salary')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig('docs/demo/quality_report.png')
        plt.close()
    except Exception:
        pass


def make_top_skills_png(conn):
    ensure_dirs()
    try:
        if not _HAS_MATPLOTLIB:
            print('matplotlib not installed; skipping PNG generation for top skills chart')
            return
        sql = '''
        SELECT ds.skill_name, COUNT(*) AS cnt
        FROM dim_skill ds
        JOIN fact_job_skills fjs ON ds.skill_key = fjs.skill_key
        GROUP BY ds.skill_name
        ORDER BY cnt DESC
        LIMIT 10
        '''
        df = query_df(conn, sql)
        if df.empty:
            return
        plt.figure(figsize=(8,4))
        plt.bar(df['skill_name'], df['cnt'])
        plt.xticks(rotation=45, ha='right')
        plt.title('Top Skills')
        plt.tight_layout()
        plt.savefig('docs/demo/warehouse_tables.png')
        plt.close()
    except Exception:
        pass


def main():
    db_path = Path('data/warehouse/demo.db')
    if not db_path.exists():
        print('Demo DB not found. Run scripts/demo_run.py first.')
        return
    conn = sqlite3.connect(str(db_path))
    export_tables(conn)
    make_quality_png(conn)
    make_top_skills_png(conn)
    conn.close()
    print('Demo artifacts generated in docs/demo/')


if __name__ == '__main__':
    main()
