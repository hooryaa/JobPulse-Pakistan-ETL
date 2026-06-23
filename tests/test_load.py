import pandas as pd
from etl.load import upsert_dataframe, get_engine, ensure_schema
import os


def test_ensure_schema_sqlite(tmp_path):
    # Use sqlite for local test
    db = f"sqlite:///{tmp_path/ 'test.db'}"
    engine = get_engine(db)
    ensure_schema(engine)
    # reflect should find tables
    meta = engine.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert len(meta) > 0
def test_placeholder():
    # Placeholder for DB load tests; to run these set DATABASE_URL in env
    assert True
