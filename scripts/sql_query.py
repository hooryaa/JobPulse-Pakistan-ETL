"""Simple SQLite query helper for demos.

Usage:
  python scripts/sql_query.py

This prints the top 10 rows from `vw_top_skills` and the list of tables.
"""
import sqlite3
from pathlib import Path

DB = Path('data/warehouse/jobpulse.db')

def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]

def top_skills(conn, limit=10):
    cur = conn.cursor()
    try:
        cur.execute('SELECT skill, count FROM vw_top_skills LIMIT ?', (limit,))
    except Exception:
        return []
    return cur.fetchall()


def main():
    if not DB.exists():
        print('Database not found at', DB)
        return
    conn = sqlite3.connect(str(DB))
    print('Tables:')
    for t in list_tables(conn):
        print(' -', t)
    print('\nTop skills (skill, count):')
    for skill, cnt in top_skills(conn, limit=10):
        print(f' - {skill}: {cnt}')
    conn.close()


if __name__ == '__main__':
    main()
