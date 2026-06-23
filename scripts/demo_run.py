"""Run an end-to-end demo using SQLite as the warehouse to produce demo artifacts.

This avoids requiring a local Postgres server while producing the same
downstream artifacts (quality report, CSV exports, and PNG screenshots)
that are useful for portfolio presentation.
"""
import os
from pathlib import Path
import json

# ensure we use SQLite for demo
os.environ['DATABASE_URL'] = 'sqlite:///data/warehouse/demo.db'

# when running from the scripts/ folder, ensure the project root is on sys.path
import sys
proj_root = Path(__file__).resolve().parents[1]
if str(proj_root) not in sys.path:
    sys.path.insert(0, str(proj_root))

from etl.pipeline import Pipeline


def run_demo():
    Path('data/warehouse').mkdir(parents=True, exist_ok=True)
    cfg_path = 'config/config.json'
    with open(cfg_path) as f:
        cfg = json.load(f)
    pipeline = Pipeline(cfg.get('default', {}))
    summary = pipeline.run()
    print('Demo pipeline finished')
    print(summary)


if __name__ == '__main__':
    run_demo()
