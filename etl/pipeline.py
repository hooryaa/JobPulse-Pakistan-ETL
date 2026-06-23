import os
import time
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
# Avoid importing SQLAlchemy at module import time to prevent runtime import issues
import pandas as pd
import sqlite3

from .extract import get_connector
from .transform import transform_jobs
from .skills import extract_from_record
from .quality_checks import run_quality_checks, save_report
from .load import (
    get_engine,
    ensure_schema,
    upsert_dim_table,
    load_fact_job_postings,
    load_fact_job_skills,
    create_pg_engine,
)

LOGGER = logging.getLogger("jobpulse.pipeline")
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)
handler = logging.FileHandler(LOG_DIR / 'pipeline.log')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)


class Pipeline:
    def __init__(self, config: dict):
        load_dotenv()
        self.config = config
        self.connector = get_connector(config.get('source', 'remoteok'))
        self.db_url = os.getenv('DATABASE_URL') or config.get('database', {}).get('url')
        self.engine = None
        if self.db_url:
            # prefer Postgres engine with pooling
            try:
                self.engine = create_pg_engine(self.db_url)
            except Exception:
                self.engine = get_engine(self.db_url)

    def run(self):
        start_ts = time.time()
        LOGGER.info("pipeline_start: starting run")
        raw = self.connector.fetch()
        rows_extracted = len(raw)
        LOGGER.info("rows_extracted: %d", rows_extracted)

        df = transform_jobs(raw)
        rows_transformed = len(df)
        LOGGER.info("rows_transformed: %d", rows_transformed)

        # Quality checks on staging
        quality = run_quality_checks(df)
        save_report(quality, path='docs/reports/quality_report.json')
        LOGGER.info("quality_report: %s", json.dumps(quality))

        rows_loaded = 0
        if self.engine:
            ensure_schema(self.engine)

            # Prepare dimension dataframes
            dim_company_df = df[['company_name']].dropna().drop_duplicates().rename(columns={'company_name': 'company_name'})
            dim_job_df = df[['job_title', 'seniority']].drop_duplicates().rename(columns={'job_title': 'job_title', 'seniority': 'seniority_level'})
            # Use normalized city/state/country produced by transform
            # include normalized_location for robust deduplication and mapping
            dim_location_df = df[['city', 'state', 'country', 'normalized_location', 'remote_type']].drop_duplicates().rename(columns={'city': 'city', 'remote_type':'remote_type'})
            # upsert dims
            upsert_dim_table(self.engine, 'dim_company', dim_company_df, ['company_name'])
            upsert_dim_table(self.engine, 'dim_job', dim_job_df, ['job_title'])
            # Use normalized_location as the unique identifier when available
            upsert_dim_table(self.engine, 'dim_location', dim_location_df, ['normalized_location'])
            # collect skills from staged data and upsert into dim_skill
            all_skills = set()
            for s in df['skills'].dropna().tolist():
                if isinstance(s, list):
                    all_skills.update(s)
            if all_skills:
                dim_skill_df = pd.DataFrame([{'skill_name': s, 'skill_category': None} for s in sorted(all_skills)])
                upsert_dim_table(self.engine, 'dim_skill', dim_skill_df, ['skill_name'])

            # build maps from dim values to keys
            company_map = {}
            job_map = {}
            location_map = {}
            # If using sqlite3 connection, build maps with sqlite queries
            if isinstance(self.engine, sqlite3.Connection):
                try:
                    cur = self.engine.cursor()
                    cur.execute("SELECT company_name, company_key FROM dim_company")
                    company_map = {row[0]: row[1] for row in cur.fetchall()}
                    cur.execute("SELECT job_title, job_key FROM dim_job")
                    job_map = {row[0]: row[1] for row in cur.fetchall()}
                    # Prefer normalized_location mapping if present
                    cur.execute("SELECT normalized_location, location_key, city FROM dim_location")
                    location_rows = cur.fetchall()
                    # map key -> location_key, prefer normalized_location, fallback to city
                    location_map = { (r[0] or r[2]): r[1] for r in location_rows }
                except Exception:
                    LOGGER.exception("Failed to build dim maps from sqlite connection")
                    company_map = {}
                    job_map = {}
                    location_map = {}
            else:
                meta = None
                try:
                    from sqlalchemy import MetaData, Table
                    meta = MetaData(bind=self.engine)
                    meta.reflect()
                    conn = self.engine.connect()

                    # use raw SQL to avoid importing SQLAlchemy selectors at module import time
                    company_rows = conn.execute("SELECT company_name, company_key FROM dim_company").fetchall()
                    job_rows = conn.execute("SELECT job_title, job_key FROM dim_job").fetchall()
                    location_rows = conn.execute("SELECT normalized_location, location_key, city FROM dim_location").fetchall()

                    company_map = {r[0]: r[1] for r in company_rows}
                    job_map = {r[0]: r[1] for r in job_rows}
                    location_map = { (r[0] or r[2]): r[1] for r in location_rows }
                    conn.close()
                except Exception as e:
                    LOGGER.exception("Failed to build dim maps: %s", e)
                    company_map = {}
                    job_map = {}
                    location_map = {}

            # Construct fact dataframe
            fact_rows = []
            posting_skill_pairs = []
            for _, row in df.iterrows():
                posting_id = str(row.get('posting_id') or row.get('posting_id'))
                job_key = job_map.get(row.get('job_title'))
                company_key = company_map.get(row.get('company_name'))
                # prefer normalized_location for lookup, fallback to city
                location_key = location_map.get(row.get('normalized_location') or row.get('city'))
                # simplistic date handling; use load date
                date_key = None
                fact_rows.append({
                    'posting_id': posting_id,
                    'job_key': job_key,
                    'company_key': company_key,
                    'location_key': location_key,
                    'date_key': date_key,
                    'salary_min': row.get('salary_min'),
                    'salary_max': row.get('salary_max'),
                    'salary_avg': row.get('salary_avg'),
                    'posting_count': 1,
                })
                # extract skills and queue for insertion after we have posting_key
                skills = row.get('skills') or []
                for sk in skills:
                    posting_skill_pairs.append((posting_id, sk))

            fact_df = pd.DataFrame(fact_rows)
            # upsert fact_job_postings
            # Note: load_fact_job_postings expects posting_id present; it will upsert by posting_id
            load_fact_job_postings(self.engine, fact_df)
            rows_loaded = len(fact_df)

            # map posting_id -> posting_key and load posting-skill pairs
            try:
                posting_map = {}
                skill_map = {}
                posting_skill_pairs_final = []
                if isinstance(self.engine, sqlite3.Connection):
                    cur = self.engine.cursor()
                    cur.execute("SELECT posting_id, posting_key FROM fact_job_postings")
                    posting_map = {r[0]: r[1] for r in cur.fetchall()}
                    cur.execute("SELECT skill_name, skill_key FROM dim_skill")
                    skill_map = {r[0]: r[1] for r in cur.fetchall()}
                    for posting_id, skill_name in posting_skill_pairs:
                        pk = posting_map.get(posting_id)
                        sk = skill_map.get(skill_name)
                        if pk and sk:
                            posting_skill_pairs_final.append((pk, sk))
                    if posting_skill_pairs_final:
                        load_fact_job_skills(self.engine, posting_skill_pairs_final)
                else:
                    conn = self.engine.connect()
                    posting_rows = conn.execute("SELECT posting_id, posting_key FROM fact_job_postings").fetchall()
                    skill_rows = conn.execute("SELECT skill_name, skill_key FROM dim_skill").fetchall()
                    conn.close()
                    posting_map = {r[0]: r[1] for r in posting_rows}
                    skill_map = {r[0]: r[1] for r in skill_rows}
                    for posting_id, skill_name in posting_skill_pairs:
                        pk = posting_map.get(posting_id)
                        sk = skill_map.get(skill_name)
                        if pk and sk:
                            posting_skill_pairs_final.append((pk, sk))
                    if posting_skill_pairs_final:
                        load_fact_job_skills(self.engine, posting_skill_pairs_final)
            except Exception:
                LOGGER.exception("Failed to load posting-skill relationships")

        duration = time.time() - start_ts
        summary = {
            'pipeline_start': start_ts,
            'pipeline_end': time.time(),
            'rows_extracted': rows_extracted,
            'rows_transformed': rows_transformed,
            'rows_loaded': rows_loaded,
            'duration_seconds': duration,
            'quality': quality,
        }
        # normalize summary values to native Python types to avoid NumPy serialization issues
        def _normalize(o):
            try:
                if hasattr(o, 'item'):
                    return o.item()
            except Exception:
                pass
            if isinstance(o, dict):
                return {k: _normalize(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_normalize(x) for x in o]
            return o

        summary = _normalize(summary)
        Path('logs').mkdir(exist_ok=True)
        with open('logs/pipeline_summary.json', 'w', encoding='utf8') as f:
            json.dump(summary, f, indent=2)
        LOGGER.info("pipeline_end: %s", json.dumps(summary))
        return summary


def from_config_file(path: str):
    import json
    with open(path) as f:
        cfg = json.load(f)
    return Pipeline(cfg.get('default', {}))

