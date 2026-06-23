"""Run a quick Rozee connector proof-of-concept and print saved files.

Usage: python scripts/run_rozee_poc.py
"""
import importlib.util
from pathlib import Path

# Load connectors/rozee.py as a module without relying on package imports
spec = importlib.util.spec_from_file_location('rozee', str(Path(__file__).resolve().parents[1] / 'connectors' / 'rozee.py'))
rozee = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rozee)


def main():
    # example search URLs - iterate over categories to gather volume
    search_urls = [
        'https://www.rozee.pk/job/jsearch/q/software-developer',
        'https://www.rozee.pk/job/jsearch/q/backend-developer',
        'https://www.rozee.pk/job/jsearch/q/frontend-developer',
        'https://www.rozee.pk/job/jsearch/q/data-scientist',
        'https://www.rozee.pk/job/jsearch/q/data-analyst',
        'https://www.rozee.pk/job/jsearch/q/devops',
        'https://www.rozee.pk/job/jsearch/q/qa-engineer',
        'https://www.rozee.pk/job/jsearch/q/project-manager',
        'https://www.rozee.pk/job/jsearch/q/product-manager',
        'https://www.rozee.pk/job/jsearch/q/graphic-designer'
    ]

    target_valid = 100
    max_rounds = 20
    total_attempted = 0
    total_saved = []

    for rnd in range(max_rounds):
        for url in search_urls:
            attempted, saved = rozee.fetch_search(url, max_items=20, delay=1.0)
            total_attempted += attempted
            total_saved.extend(saved)
            print(f'Round {rnd+1} URL {url}: attempted={attempted}, saved={len(saved)}')
            if len(total_saved) >= target_valid:
                break
        if len(total_saved) >= target_valid:
            break

    # Deduplicate saved paths
    total_saved = list(dict.fromkeys(total_saved))
    total = len(total_saved)
    usable_pct = (total / total_attempted * 100) if total_attempted else 0
    print('Scrape summary: total_attempted_links=', total_attempted, 'valid_saved=', total, f'usable_pct={usable_pct:.1f}%')

    # sanity gate: do not proceed to transform if usable percentage is very low
    if usable_pct < 30:
        print('Stopping: too many low-quality captures (usable_pct < 30%). Collect more data or adjust filters.')
    else:
        print('Saved:', total_saved)
        # proceed to run transform and charts
        try:
            import subprocess
            subprocess.run(['c:/workspace/jobpulse/.venv/Scripts/python.exe', '-m', 'etl.transform'], check=True)
            subprocess.run(['c:/workspace/jobpulse/.venv/Scripts/python.exe', 'scripts/generate_charts.py'], check=True)
        except Exception as e:
            print('Error running transform/charts:', e)


if __name__ == '__main__':
    main()