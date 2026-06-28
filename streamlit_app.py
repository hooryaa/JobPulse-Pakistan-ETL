from collections import Counter
from pathlib import Path
import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'warehouse' / 'jobpulse.db'
STAGING_PATH = ROOT / 'data' / 'staging' / 'job_postings.csv'
INSIGHTS_PATH = ROOT / 'reports' / 'latest' / 'insights_summary.json'


def load_staging_data() -> pd.DataFrame:
    if not STAGING_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(STAGING_PATH)
    df.columns = [c.strip() for c in df.columns]
    df['salary_min'] = pd.to_numeric(df.get('salary_min'), errors='coerce')
    df['salary_max'] = pd.to_numeric(df.get('salary_max'), errors='coerce')
    if 'salary_avg' not in df.columns:
        df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)
    df['skills'] = df['skills'].fillna('').astype(str)
    df['skill_list'] = df['skills'].str.split(';').apply(lambda values: [s.strip() for s in values if s.strip()])
    df['skills_search'] = df['skills'].str.lower()
    return df


@st.cache_data
def load_insights() -> dict:
    if not INSIGHTS_PATH.exists():
        return {}
    try:
        return json.loads(INSIGHTS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def build_skill_counts(df: pd.DataFrame) -> pd.Series:
    skills = [skill for skills in df['skill_list'] for skill in skills]
    return pd.Series(Counter(skills)).sort_values(ascending=False)


def filter_jobs(df: pd.DataFrame, selected_cities, selected_companies, selected_skills, text_search, salary_range):
    if selected_cities:
        df = df[df['city'].isin(selected_cities)]
    if selected_companies:
        df = df[df['company'].isin(selected_companies)]
    if selected_skills:
        skill_pattern = '|'.join(re.escape(skill) for skill in selected_skills)
        df = df[df['skills_search'].str.contains(skill_pattern, na=False, case=False)]
    if text_search:
        query = re.escape(text_search.lower())
        df = df[df['skills_search'].str.contains(query, na=False, case=False)]
    if salary_range is not None and 'salary_avg' in df.columns:
        df = df[df['salary_avg'].between(salary_range[0], salary_range[1], inclusive='both')]
    return df


def render_metrics(df: pd.DataFrame, insights: dict):
    total_jobs = len(df)
    jobs_with_skills = int(df['skills'].astype(bool).sum())
    skill_coverage_pct = round(jobs_with_skills / total_jobs * 100, 1) if total_jobs else 0.0
    salary_stats = df['salary_avg'].dropna()
    avg_salary = round(float(salary_stats.mean()), 0) if not salary_stats.empty else None
    median_salary = round(float(salary_stats.median()), 0) if not salary_stats.empty else None

    st.subheader('Live JobPulse Metrics')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Total Job Postings', total_jobs)
    col2.metric('Jobs with Skills', jobs_with_skills, f'{skill_coverage_pct}% coverage')
    col3.metric('Average Salary', f'PKR {avg_salary:,.0f}' if avg_salary is not None else 'N/A')
    col4.metric('Median Salary', f'PKR {median_salary:,.0f}' if median_salary is not None else 'N/A')

    if insights.get('data_quality'):
        dq = insights['data_quality']
        st.markdown('**Data quality snapshot**')
        st.write({
            'Total postings': dq.get('total_postings'),
            'Postings with skills': dq.get('postings_with_skills'),
            'Skill coverage': f"{dq.get('skill_coverage_pct', 0):.1f}%",
            'Top skill': dq.get('top_skill'),
            'Gate status': 'PASSED' if dq.get('passed') else 'FAILED',
        })


def render_charts(df: pd.DataFrame):
    if df.empty:
        st.warning('No staging data is available. Run `python run_pipeline.py` first.')
        return

    skill_counts = build_skill_counts(df)
    city_counts = df['city'].fillna('Unknown').value_counts()
    company_counts = df['company'].fillna('Unknown').value_counts()

    with st.expander('Top Visualizations', expanded=True):
        chart1, chart2 = st.columns(2)
        if not skill_counts.empty:
            fig_skills = px.bar(
                skill_counts.head(15).sort_values(),
                orientation='h',
                title='Top Skills',
                labels={'index': 'Skill', 'value': 'Postings'},
            )
            fig_skills.update_layout(yaxis={'categoryorder': 'total ascending'})
            chart1.plotly_chart(fig_skills, use_container_width=True)
        else:
            chart1.info('No skill counts available yet.')

        fig_cities = px.bar(
            city_counts.head(15).sort_values(ascending=True),
            orientation='h',
            title='Jobs by City',
            labels={'index': 'City', 'value': 'Postings'},
        )
        fig_cities.update_layout(yaxis={'categoryorder': 'total ascending'})
        chart2.plotly_chart(fig_cities, use_container_width=True)

    with st.expander('Salary Insights', expanded=False):
        salary_df = df[['salary_min', 'salary_max', 'salary_avg']].dropna()
        if not salary_df.empty:
            fig_salary = px.histogram(
                salary_df,
                x='salary_avg',
                nbins=25,
                title='Salary Distribution (average)',
                labels={'salary_avg': 'Salary (PKR)'},
            )
            st.plotly_chart(fig_salary, use_container_width=True)
            st.write('Salary summary:')
            st.write(salary_df['salary_avg'].describe().round(0).to_dict())
        else:
            st.info('No salary data available to visualize.')

    with st.expander('Company Activity', expanded=False):
        fig_companies = px.bar(
            company_counts.head(15).sort_values(ascending=True),
            orientation='h',
            title='Top Hiring Companies',
            labels={'index': 'Company', 'value': 'Postings'},
        )
        fig_companies.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_companies, use_container_width=True)


def render_job_table(df: pd.DataFrame):
    if df.empty:
        st.info('No jobs match the current filters.')
        return

    display_df = df.copy()
    display_cols = ['title', 'company', 'city', 'normalized_location', 'salary_min', 'salary_max', 'skills']
    display_cols = [c for c in display_cols if c in display_df.columns]
    st.markdown('### Filtered job postings')
    st.dataframe(display_df[display_cols].head(50), use_container_width=True)


def main():
    st.set_page_config(page_title='JobPulse Dashboard', page_icon='📊', layout='wide')

    st.title('JobPulse Interactive Dashboard')
    st.markdown(
        'A lightweight interactive dashboard for recruiter-facing analytics. '
        'Filter jobs, explore top skills, review salary trends, and inspect data quality in one live view.'
    )

    insights = load_insights()
    df = load_staging_data()

    if df.empty:
        st.warning('Staging data not found. Run `python run_pipeline.py` to generate `data/staging/job_postings.csv` and `data/warehouse/jobpulse.db`.')

    cities = sorted(df['city'].dropna().unique()) if 'city' in df.columns else []
    companies = sorted(df['company'].dropna().unique()) if 'company' in df.columns else []
    skill_counts = build_skill_counts(df)
    skill_options = skill_counts.index.tolist()[:50]

    with st.sidebar:
        st.header('Filters')
        selected_cities = st.multiselect('Cities', options=cities, default=cities[:6])
        selected_companies = st.multiselect('Companies', options=companies, default=companies[:6])
        selected_skills = st.multiselect('Skills', options=skill_options, default=skill_options[:5])
        text_search = st.text_input('Search skills', '')

        salary_min = float(df['salary_avg'].min()) if 'salary_avg' in df.columns else 0.0
        salary_max = float(df['salary_avg'].max()) if 'salary_avg' in df.columns else 0.0
        if salary_min < salary_max:
            salary_range = st.slider(
                'Salary range (PKR average)',
                min_value=float(salary_min),
                max_value=float(salary_max),
                value=(float(salary_min), float(salary_max)),
                step=max(1000.0, (salary_max - salary_min) / 100),
            )
        else:
            salary_range = None

        st.markdown('---')
        st.markdown('**Quick actions**')
        st.write('Run pipeline:')
        st.code('python run_pipeline.py')
        st.write('Launch dashboard:')
        st.code('streamlit run streamlit_app.py')

    filtered_df = filter_jobs(df, selected_cities, selected_companies, selected_skills, text_search, salary_range)

    render_metrics(filtered_df, insights)
    render_charts(filtered_df)
    render_job_table(filtered_df)

    st.markdown('---')
    st.markdown(
        '**Repo**: [hooryaa/JobPulse-Pakistan-ETL](https://github.com/hooryaa/JobPulse-Pakistan-ETL)  \n'
        '**Portfolio**: [https://hooria-portfolio.vercel.app/](https://hooria-portfolio.vercel.app/)'
    )


if __name__ == '__main__':
    main()
