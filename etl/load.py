import logging
from pathlib import Path
from typing import Iterable
import sqlite3

import pandas as pd

LOGGER = logging.getLogger("jobpulse.load")


# Attempt to import SQLAlchemy; if it fails (or has runtime issues), fall back to sqlite.
try:
    from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, String,
                            Float, Date, Boolean)
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    SQLALCHEMY_AVAILABLE = True
except Exception:
    SQLALCHEMY_AVAILABLE = False


def get_engine(db_url: str):
    """Return a DB engine/connection. For sqlite URLs we return a sqlite3.Connection.

    For other URLs, attempt to return a SQLAlchemy engine if available.
    """
    if db_url.startswith("sqlite://"):
        path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(path)
        return conn
    if SQLALCHEMY_AVAILABLE:
        return create_engine(db_url)
    raise RuntimeError("SQLAlchemy required for non-sqlite databases")


def ensure_schema(engine):
    """Create minimal schema. Accepts either SQLAlchemy engine or sqlite3.Connection."""
    # Minimal SQL statements for fallback
    stmts = [
        "CREATE TABLE IF NOT EXISTS dim_company (company_key INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL UNIQUE, industry TEXT, company_size TEXT);",
        "CREATE TABLE IF NOT EXISTS dim_location (location_key INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, state TEXT, city TEXT, remote_type TEXT);",
        "CREATE TABLE IF NOT EXISTS dim_skill (skill_key INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL UNIQUE, skill_category TEXT);",
        "CREATE TABLE IF NOT EXISTS dim_date (date_key INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL UNIQUE, day INTEGER, month INTEGER, quarter INTEGER, year INTEGER);",
        "CREATE TABLE IF NOT EXISTS dim_job (job_key INTEGER PRIMARY KEY AUTOINCREMENT, job_title TEXT NOT NULL, job_category TEXT, seniority_level TEXT);",
        "CREATE TABLE IF NOT EXISTS fact_job_postings (posting_key INTEGER PRIMARY KEY AUTOINCREMENT, posting_id TEXT NOT NULL UNIQUE, job_key INTEGER, company_key INTEGER, location_key INTEGER, date_key INTEGER, salary_min REAL, salary_max REAL, salary_avg REAL, posting_count INTEGER DEFAULT 1);",
        "CREATE TABLE IF NOT EXISTS fact_job_skills (id INTEGER PRIMARY KEY AUTOINCREMENT, posting_key INTEGER NOT NULL, skill_key INTEGER NOT NULL);",
    ]
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        for s in stmts:
            cur.execute(s)
        engine.commit()
        return
    if SQLALCHEMY_AVAILABLE:
        meta = MetaData()
        # Minimal dims and fact for demo using SQLAlchemy Table objects
        dim_company = Table('dim_company', meta,
                            Column('company_key', Integer, primary_key=True),
                            Column('company_name', String, nullable=False),
                            Column('industry', String),
                            Column('company_size', String),
                            )

        dim_location = Table('dim_location', meta,
                             Column('location_key', Integer, primary_key=True),
                             Column('country', String),
                             Column('state', String),
                             Column('city', String),
                             Column('remote_flag', String),
                             )

        dim_skill = Table('dim_skill', meta,
                          Column('skill_key', Integer, primary_key=True),
                          Column('skill_name', String, nullable=False),
                          Column('skill_category', String),
                          )

        dim_date = Table('dim_date', meta,
                         Column('date_key', Integer, primary_key=True),
                         Column('date', Date),
                         Column('day', Integer),
                         Column('month', Integer),
                         Column('quarter', Integer),
                         Column('year', Integer),
                         )

        dim_job = Table('dim_job', meta,
                        Column('job_key', Integer, primary_key=True),
                        Column('job_title', String),
                        Column('job_category', String),
                        Column('seniority_level', String),
                        )

        fact_job_postings = Table('fact_job_postings', meta,
                                  Column('posting_key', Integer, primary_key=True),
                                  Column('job_key', Integer),
                                  Column('company_key', Integer),
                                  Column('location_key', Integer),
                                  Column('date_key', Integer),
                                  Column('salary_min', Float),
                                  Column('salary_max', Float),
                                  Column('salary_avg', Float),
                                  Column('posting_count', Integer),
                                  )

        meta.create_all(engine)
        return
    raise RuntimeError("No available backend to create schema")


def upsert_dataframe(engine, table_name: str, df: pd.DataFrame, pk: str):
    """Simple upsert: supports sqlite3.Connection fallback and SQLAlchemy engines (best-effort)."""
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        # create table if not exists with basic columns
        cols = df.columns.tolist()
        # naive schema: all text
        create_cols = ', '.join([f'"{c}" TEXT' for c in cols])
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({create_cols});')
        # insert rows
        placeholders = ','.join(['?'] * len(cols))
        insert_sql = f'INSERT INTO "{table_name}" ({",".join(cols)}) VALUES ({placeholders})'
        for _, row in df.iterrows():
            cur.execute(insert_sql, [str(x) if x is not None else None for x in row.tolist()])
        engine.commit()
        LOGGER.info("Inserted %d rows into %s (sqlite fallback)", len(df), table_name)
        return
    if SQLALCHEMY_AVAILABLE:
        meta = MetaData(bind=engine)
        meta.reflect()
        table = meta.tables.get(table_name)
        if table is None:
            raise ValueError(f"Table {table_name} not found in database")
        conn = engine.connect()
        inserted = 0
        for _, row in df.iterrows():
            stmt = pg_insert(table).values(**row.to_dict())
            if pk:
                stmt = stmt.on_conflict_do_update(index_elements=[pk], set_=row.to_dict())
            conn.execute(stmt)
            inserted += 1
        conn.close()
        LOGGER.info("Upserted %d rows into %s", inserted, table_name)
        return
    raise RuntimeError("No available backend to upsert data")


def create_pg_engine(db_url: str, pool_size: int = 5, max_overflow: int = 10):
    if not SQLALCHEMY_AVAILABLE:
        raise RuntimeError("SQLAlchemy is required for Postgres engine creation")
    # check for DBAPI availability (psycopg2) and provide actionable message
    try:
        import psycopg2  # noqa: F401
    except Exception:
        raise RuntimeError(
            "psycopg2 is required to connect to PostgreSQL.\n"
            "Install it in your environment: \n"
            "  python -m pip install psycopg2-binary\n"
            "Or, using the project's venv on Windows: \n"
            "  c:/workspace/jobpulse/.venv/Scripts/python.exe -m pip install psycopg2-binary"
        )
    return create_engine(db_url, pool_size=pool_size, max_overflow=max_overflow)


def upsert_dim_table(engine, table_name: str, df: pd.DataFrame, unique_cols: list):
    """Upsert dataframe rows into a dimension table using Postgres ON CONFLICT."""
    # SQLite fallback implementation
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        # ensure table exists with columns from df (naive approach)
        cols = df.columns.tolist()
        if cols:
            col_defs = ', '.join([f'"{c}" TEXT' for c in cols])
            try:
                cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs});')
            except Exception:
                # if table already exists with different schema, ignore
                pass

        for rec in df.to_dict(orient='records'):
            # ensure table has necessary columns; add missing ones as TEXT
            try:
                cur.execute(f'PRAGMA table_info("{table_name}")')
                existing_cols = [r[1] for r in cur.fetchall()]
            except Exception:
                existing_cols = []
            for col in rec.keys():
                if col not in existing_cols:
                    try:
                        cur.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" TEXT')
                    except Exception:
                        # ignore failures (e.g., unsupported types or existing column)
                        pass
            # build where clause from unique_cols
            where_clauses = []
            values = []
            for c in unique_cols:
                where_clauses.append(f'"{c}" = ?')
                values.append(rec.get(c))
            where_sql = ' AND '.join(where_clauses) if where_clauses else '1=0'
            cur.execute(f'SELECT rowid FROM "{table_name}" WHERE {where_sql}', values)
            existing = cur.fetchone()
            if existing:
                # update existing row
                set_cols = [f'"{k}" = ?' for k in rec.keys() if k not in unique_cols]
                set_vals = [rec[k] for k in rec.keys() if k not in unique_cols]
                if set_cols:
                    sql = f'UPDATE "{table_name}" SET {",".join(set_cols)} WHERE {where_sql}'
                    cur.execute(sql, set_vals + values)
            else:
                # insert new row
                cols = ','.join([f'"{k}"' for k in rec.keys()])
                placeholders = ','.join(['?'] * len(rec.keys()))
                cur.execute(f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders})', list(rec.values()))
        engine.commit()
        LOGGER.info('Upserted %d rows into %s (sqlite fallback)', len(df), table_name)
        return
    meta = MetaData(bind=engine)
    meta.reflect()
    table = meta.tables.get(table_name)
    if table is None:
        raise ValueError(f"Table {table_name} not found")
    records = df.to_dict(orient='records')
    with engine.begin() as conn:
        for rec in records:
            # Build insert statement with on_conflict
            stmt = pg_insert(table).values(**rec)
            conflict_cols = unique_cols
            update_cols = {k: rec[k] for k in rec.keys() if k not in conflict_cols}
            if update_cols:
                stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
            conn.execute(stmt)


def load_fact_job_postings(engine, df: pd.DataFrame):
    """Load fact_job_postings DataFrame into warehouse, idempotent via posting_id unique constraint."""
    # sqlite fallback
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        # ensure posting_id column exists
        try:
            cur.execute("PRAGMA table_info('fact_job_postings')")
            cols = [r[1] for r in cur.fetchall()]
        except Exception:
            cols = []
        if 'posting_id' not in cols:
            try:
                cur.execute("ALTER TABLE fact_job_postings ADD COLUMN posting_id TEXT")
            except Exception:
                pass
        for rec in df.to_dict(orient='records'):
            posting_id = rec.get('posting_id')
            if posting_id is None:
                # skip rows without business key
                continue
            cur.execute('SELECT posting_key FROM fact_job_postings WHERE posting_id = ?', (posting_id,))
            existing = cur.fetchone()
            cols = [k for k in rec.keys() if k != 'posting_key']
            if existing:
                # update
                set_cols = [f'"{c}" = ?' for c in cols if c != 'posting_id']
                vals = [rec[c] for c in cols if c != 'posting_id']
                if set_cols:
                    sql = f'UPDATE fact_job_postings SET {",".join(set_cols)} WHERE posting_id = ?'
                    cur.execute(sql, vals + [posting_id])
            else:
                insert_cols = ','.join([f'"{c}"' for c in cols])
                placeholders = ','.join(['?'] * len(cols))
                cur.execute(f'INSERT INTO fact_job_postings ({insert_cols}) VALUES ({placeholders})', [rec[c] for c in cols])
        engine.commit()
        LOGGER.info('Loaded %d fact_job_postings (sqlite fallback)', len(df))
        return
    if not SQLALCHEMY_AVAILABLE:
        raise RuntimeError("SQLAlchemy required for loading to Postgres")
    meta = MetaData(bind=engine)
    meta.reflect()
    table = meta.tables.get('fact_job_postings')
    if table is None:
        raise ValueError("fact_job_postings table not found")
    records = df.to_dict(orient='records')
    with engine.begin() as conn:
        for rec in records:
            stmt = pg_insert(table).values(**rec)
            # exclude posting_key (surrogate) from update set
            update_cols = {k: rec[k] for k in rec.keys() if k not in ('posting_key',)}
            stmt = stmt.on_conflict_do_update(index_elements=['posting_id'], set_=update_cols)
            conn.execute(stmt)


def load_fact_job_skills(engine, posting_skill_pairs):
    """Insert many-to-many posting_key, skill_key pairs into fact_job_skills idempotently."""
    if isinstance(engine, sqlite3.Connection):
        cur = engine.cursor()
        for posting_key, skill_key in posting_skill_pairs:
            cur.execute('SELECT 1 FROM fact_job_skills WHERE posting_key = ? AND skill_key = ?', (posting_key, skill_key))
            if not cur.fetchone():
                cur.execute('INSERT INTO fact_job_skills (posting_key, skill_key) VALUES (?, ?)', (posting_key, skill_key))
        engine.commit()
        LOGGER.info('Loaded %d posting-skill pairs (sqlite fallback)', len(posting_skill_pairs))
        return
    if not SQLALCHEMY_AVAILABLE:
        raise RuntimeError("SQLAlchemy required for loading skill facts")
    meta = MetaData(bind=engine)
    meta.reflect()
    table = meta.tables.get('fact_job_skills')
    if table is None:
        raise ValueError("fact_job_skills table not found")
    with engine.begin() as conn:
        for posting_key, skill_key in posting_skill_pairs:
            stmt = pg_insert(table).values(posting_key=posting_key, skill_key=skill_key)
            stmt = stmt.on_conflict_do_nothing(index_elements=['posting_key', 'skill_key'])
            conn.execute(stmt)
