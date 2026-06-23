"""Load staging CSVs into a local SQLite warehouse.

Usage: python scripts/run_load.py

This script performs simple data-quality checks (skill coverage) before loading
and populates dimension and fact tables in `data/warehouse/jobpulse.db`.
"""
from pathlib import Path
import pandas as pd
import sqlite3
import sys

# Ensure project root is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl import load as loader


def main():
    staging_dir = Path('data/staging')
    postings_path = staging_dir / 'job_postings.csv'
    skills_path = staging_dir / 'job_skills.csv'

    if not postings_path.exists() or not skills_path.exists():
        print('Staging files missing. Run transform first.')
        sys.exit(1)

    df_post = pd.read_csv(postings_path)
    df_skills = pd.read_csv(skills_path)

    total = len(df_post)
    postings_with_skills = df_skills['posting_id'].nunique()
    usable_pct = (postings_with_skills / total * 100) if total else 0
    dup_posts = df_post['posting_id'].duplicated().sum()

    print(f'Total postings={total}, postings_with_skills={postings_with_skills}, usable_pct={usable_pct:.1f}%, duplicates={dup_posts}')

    if usable_pct < 30:
        print('Stopping load: usable skill coverage < 30%')
        sys.exit(2)

    # prepare warehouse
    ware_dir = Path('data/warehouse')
    ware_dir.mkdir(parents=True, exist_ok=True)
    db_path = ware_dir / 'jobpulse.db'
    db_url = f'sqlite:///{db_path.absolute()}'
    engine = loader.get_engine(db_url)
    loader.ensure_schema(engine)

    # dims
    # prepare and clean dimension data (drop null/empty keys)
    df_company = df_post[['company']].drop_duplicates().rename(columns={'company': 'company_name'})
    df_company['company_name'] = df_company['company_name'].astype(str).str.strip()
    df_company = df_company[df_company['company_name'].notna() & (df_company['company_name'] != '')]
    if not df_company.empty:
        loader.upsert_dim_table(engine, 'dim_company', df_company, unique_cols=['company_name'])

    df_skill = pd.DataFrame({'skill_name': sorted([s for s in df_skills['skill'].unique() if pd.notna(s) and str(s).strip()])})
    if not df_skill.empty:
        loader.upsert_dim_table(engine, 'dim_skill', df_skill, unique_cols=['skill_name'])

    df_job = df_post[['title']].drop_duplicates().rename(columns={'title': 'job_title'})
    df_job['job_title'] = df_job['job_title'].astype(str).str.strip()
    df_job = df_job[df_job['job_title'].notna() & (df_job['job_title'] != '')]
    if not df_job.empty:
        loader.upsert_dim_table(engine, 'dim_job', df_job, unique_cols=['job_title'])

    df_location = df_post[['city']].drop_duplicates().rename(columns={'city': 'city'})
    df_location['city'] = df_location['city'].astype(str).str.strip()
    df_location = df_location[df_location['city'].notna() & (df_location['city'] != '')]
    if not df_location.empty:
        loader.upsert_dim_table(engine, 'dim_location', df_location, unique_cols=['city'])

    # facts: prepare fact_job_postings payload (posting_id is business key)
    fact = df_post.copy()
    # compute salary_avg if not present
    if 'salary_avg' not in fact.columns:
        fact['salary_avg'] = fact[['salary_min', 'salary_max']].mean(axis=1)

    # keep only columns expected by fact_job_postings (posting_id and salary fields)
    fact_cols = ['posting_id', 'salary_min', 'salary_max', 'salary_avg']
    for c in fact_cols:
        if c not in fact.columns:
            fact[c] = None
    fact_payload = fact[fact_cols]
    loader.load_fact_job_postings(engine, fact_payload)

    # Build posting_key <-> posting_id map
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        cur.execute('SELECT posting_key, posting_id FROM fact_job_postings')
        rows = cur.fetchall()
        posting_map = {r[1]: r[0] for r in rows}

        cur.execute('SELECT skill_key, skill_name FROM dim_skill')
        rows = cur.fetchall()
        skill_map = {r[1]: r[0] for r in rows}

        posting_skill_pairs = []
        for _, r in df_skills.iterrows():
            pid = str(r['posting_id'])
            skill = r['skill']
            pk = posting_map.get(pid)
            sk = skill_map.get(skill)
            if pk and sk:
                posting_skill_pairs.append((pk, sk))

        loader.load_fact_job_skills(engine, posting_skill_pairs)

    print(f'Loaded warehouse at {db_path} successfully')


if __name__ == '__main__':
    main()
