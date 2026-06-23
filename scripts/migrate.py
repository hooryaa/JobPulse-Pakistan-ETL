"""Simple migration runner to apply SQL migrations to PostgreSQL."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')


def run_migration(sql_path: str):
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL not set in environment')
    try:
        import psycopg2
    except Exception:
        raise RuntimeError(
            "psycopg2 is required to run migrations.\n"
            "Install it into your environment, e.g.:\n"
            "  python -m pip install psycopg2-binary\n"
            "Or, if using the project's venv on Windows: ".format() +
            "c:/workspace/jobpulse/.venv/Scripts/python.exe -m pip install psycopg2-binary"
        )

    with open(sql_path, 'r', encoding='utf8') as f:
        sql = f.read()
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()


if __name__ == '__main__':
    migrations_dir = Path(__file__).parent.parent / 'sql' / 'migrations'
    for p in sorted(migrations_dir.glob('*.sql')):
        print('Applying', p)
        run_migration(str(p))
    print('Migrations applied')
