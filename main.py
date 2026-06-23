import argparse
import logging
import json
from etl.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')


def load_config(path='config/config.json'):
    with open(path) as f:
        return json.load(f)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run'])
    args = parser.parse_args()
    cfg = load_config()
    p = Pipeline(cfg.get('default', {}))
    if args.command == 'run':
        p.run()


if __name__ == '__main__':
    cli()
from etl.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
