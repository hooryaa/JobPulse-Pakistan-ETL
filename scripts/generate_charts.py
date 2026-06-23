from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt


def find_latest_release_dir(releases_root: Path) -> Path:
    candidates = [d for d in releases_root.iterdir() if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)]
    if not candidates:
        return releases_root
    return sorted(candidates)[-1]


def ensure_dest(releases_root: Path) -> Path:
    latest = find_latest_release_dir(releases_root)
    dest = releases_root / 'latest' / 'screenshots'
    dest.mkdir(parents=True, exist_ok=True)
    return latest, dest


def top_skills_chart(postings_df: pd.DataFrame, skills_df: pd.DataFrame, out_path: Path):
    # build skill counts
    if not skills_df.empty:
        counts = skills_df['skill'].value_counts().head(10)
    else:
        skills_series = postings_df['skills'].dropna().astype(str).str.split(';').explode()
        counts = skills_series.str.strip().value_counts().head(10)

    if counts.empty:
        print('No skills to plot')
        return

    plt.figure(figsize=(8, 6))
    counts.sort_values().plot(kind='barh', color='C0')
    plt.title('Top 10 Skills in Pakistan Jobs')
    plt.xlabel('Postings')
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def city_distribution_chart(postings_df: pd.DataFrame, out_path: Path):
    cities = postings_df['city'].fillna('Unknown')
    counts = cities.value_counts().head(10)
    if counts.empty:
        print('No city data to plot')
        return
    plt.figure(figsize=(8, 6))
    counts.plot(kind='bar', color='C1')
    plt.title('Jobs by City')
    plt.ylabel('Postings')
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def top_companies_chart(postings_df: pd.DataFrame, out_path: Path):
    comps = postings_df['company'].fillna('Unknown')
    counts = comps.value_counts().head(10)
    if counts.empty:
        print('No company data to plot')
        return
    plt.figure(figsize=(8, 6))
    counts.sort_values().plot(kind='barh', color='C2')
    plt.title('Top Hiring Companies')
    plt.xlabel('Postings')
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def main():
    releases_root = Path('docs/releases')
    latest_release, dest = ensure_dest(releases_root)

    postings_path = Path('data/staging/job_postings.csv')
    skills_path = Path('data/staging/job_skills.csv')

    if not postings_path.exists():
        print('Posting CSV not found:', postings_path)
        return

    df = pd.read_csv(postings_path)
    if skills_path.exists():
        df_sk = pd.read_csv(skills_path)
    else:
        df_sk = pd.DataFrame(columns=['posting_id', 'skill'])

    # Validation: report counts and avoid plotting empty skills
    total_postings = len(df)
    postings_with_skills = df['skills'].notnull().sum() if 'skills' in df.columns else 0
    total_skill_rows = len(df_sk)
    print(f'Chart generator: total_postings={total_postings}, postings_with_skills={postings_with_skills}, total_skill_rows={total_skill_rows}')

    top_sk_path = dest / 'top_skills.png'
    city_path = dest / 'city_distribution.png'
    comp_path = dest / 'top_companies.png'

    if total_skill_rows > 0 or postings_with_skills > 0:
        top_skills_chart(df, df_sk, top_sk_path)
    else:
        print('Skipping top skills chart: no extracted skills present')
    city_distribution_chart(df, city_path)
    top_companies_chart(df, comp_path)

    print('Charts written to', dest)


if __name__ == '__main__':
    main()
