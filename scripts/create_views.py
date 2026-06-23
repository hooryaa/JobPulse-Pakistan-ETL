"""Create analytics SQL views in the warehouse.

This script ensures a `staging_job_postings` table exists in the SQLite
warehouse (loaded from `data/staging/job_postings.csv`) and creates three
views: `vw_top_skills`, `vw_city_demand`, `vw_company_activity`.
"""
from pathlib import Path
import pandas as pd
import sqlite3


DB_PATH = Path('data/warehouse/jobpulse.db')


def ensure_staging_table():
    staging_csv = Path('data/staging/job_postings.csv')
    if not staging_csv.exists():
        print('No staging CSV found at', staging_csv)
        return 0
    df = pd.read_csv(staging_csv)
    df.columns = [c.strip() for c in df.columns]
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    # drop existing table
    cur.execute('DROP TABLE IF EXISTS staging_job_postings')
    # create table with TEXT columns
    cols = df.columns.tolist()
    col_defs = ', '.join([f'"{c}" TEXT' for c in cols])
    cur.execute(f'CREATE TABLE staging_job_postings ({col_defs})')
    # insert rows
    placeholders = ','.join(['?'] * len(cols))
    insert_sql = f'INSERT INTO staging_job_postings ({",".join(["\""+c+"\"" for c in cols])}) VALUES ({placeholders})'
    rows = []
    for _, r in df.iterrows():
        vals = [None if pd.isna(x) else str(x) for x in r.tolist()]
        rows.append(vals)
    cur.executemany(insert_sql, rows)
    conn.commit()
    conn.close()
    print('Wrote staging_job_postings table with', len(rows), 'rows')
    return len(rows)


def create_views():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    # vw_top_skills
    cur.execute('''
    CREATE VIEW IF NOT EXISTS vw_top_skills AS
    SELECT ds.skill_name AS skill, COUNT(*) AS count,
      ROUND(COUNT(*) * 1.0 / (SELECT COUNT(DISTINCT posting_key) FROM fact_job_skills), 4) AS normalized_frequency
    FROM fact_job_skills fjs
    JOIN dim_skill ds ON ds.skill_key = fjs.skill_key
    GROUP BY ds.skill_name
    ORDER BY count DESC;
    ''')

    # vw_city_demand (use staging table)
    cur.execute('''
    CREATE VIEW IF NOT EXISTS vw_city_demand AS
    SELECT city, COUNT(*) AS job_count
    FROM staging_job_postings
    GROUP BY city
    ORDER BY job_count DESC;
    ''')

    # vw_company_activity (use staging table)
    cur.execute('''
    CREATE VIEW IF NOT EXISTS vw_company_activity AS
    SELECT company AS company_name, COUNT(*) AS job_count
    FROM staging_job_postings
    GROUP BY company
    ORDER BY job_count DESC;
    ''')

    conn.commit()
    conn.close()
    print('Views created: vw_top_skills, vw_city_demand, vw_company_activity')


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ensure_staging_table()
    create_views()


if __name__ == '__main__':
    main()
