# JobPulse — Job Market Intelligence (Recruiter Overview)

JobPulse is a polished, recruiter-facing data engineering portfolio project that ingests job postings, extracts skills and metadata, and loads a dimensional (star) warehouse for analytics and dashboards.

This README focuses on the product story, business value, and quick artifacts a recruiter or hiring manager will care about.

**Quick demo (no Postgres required)**

1. Activate the venv.
2. Run the demo (creates a local SQLite warehouse):

```powershell
python scripts/demo_run.py
```

3. Generate recruiter-ready artifacts (CSV, JSON, charts):

```powershell
python scripts/generate_business_insights.py
```

Artifacts and visual assets are written to `docs/demo/` and diagrams to `docs/diagrams/`.

**Where to look (high-value files)**

- Architecture diagram: [docs/diagrams/etl_architecture.mmd](docs/diagrams/etl_architecture.mmd)
- Star schema diagram: [docs/diagrams/star_schema.mmd](docs/diagrams/star_schema.mmd)
- Business insights report: [docs/business_insights.md](docs/business_insights.md)
- Demo artifacts and charts: [docs/demo/](docs/demo/)
- SQL schema & migrations: [sql/schema.sql](sql/schema.sql)

**Architecture (one-liner)**

RemoteOK → Raw JSON → Staging (parquet/CSV) → Transform (normalize, extract skills) → Warehouse (star schema: dims + facts) → Analytics (CSV/Power BI)

**Executive summary (what this project demonstrates)**

- End-to-end ETL orchestration with idempotent loads and schema migrations.
- Dimensional star schema (surrogate keys, PK/FK, indexes) suitable for analytics.
- Skill extraction and many-to-many `fact_job_skills` for technology-demand analysis.
- Data quality checks and structured pipeline reporting.
- Analytics-ready CSV exports for Power BI and dashboarding.

**Dashboard preview (examples in docs/demo/)**

- `top_skills.png` — Top extracted skills (frequency)
- `remote_distribution.png` — Remote vs Hybrid vs On-site breakdown
- `top_companies.png` — Top hiring companies
- `job_categories.png` — Popular job titles

**Business insights**

See [docs/business_insights.md](docs/business_insights.md) for a recruiter-friendly one-page report with totals, top skills, hiring companies, locations, remote trends, and salary summary where available.

**Key features (bullet list for recruiters)**

- Data ingestion from public API (RemoteOK) with retries and raw archival.
- Robust transform layer: normalization, salary parsing, seniority detection, skill extraction.
- Warehouse design: dim_company, dim_job, dim_location, dim_skill, dim_date + facts.
- Idempotent upserts using SQLAlchemy (Postgres) and a SQLite demo fallback.
- Data quality framework that generates JSON reports and summary metrics.
- Exports and visuals prepared for business stakeholders and Power BI.

**Technology stack**

- Python (ETL orchestration) — pandas, SQLAlchemy, psycopg2
- PostgreSQL (production warehouse) — schema & migrations provided
- SQLite (local demo) — reproducible demo without infra
- CSV / PNG exports — ready for Power BI or slide decks

**ETL Workflow (high level)**

1. Extract: fetch listings, save raw JSON.
2. Transform: clean fields, extract skills, classify remote and seniority.
3. Quality: run validation checks and produce `quality_report.json`.
4. Load: upsert dimensions and load fact tables (Postgres or SQLite demo).
5. Export: CSVs for dashboards and summary artifacts for recruiters.

**Data Quality Framework (what recruiters should know)**

- The pipeline computes a quality score and detailed counts (nulls, duplicates, invalid salaries).
- All numeric and NumPy types are converted to native Python types for portable JSON outputs.

**Sample SQL queries (for analytics interviews)**

- Top skills:
	- `SELECT ds.skill_name, COUNT(*) FROM dim_skill ds JOIN fact_job_skills fjs ON ds.skill_key = fjs.skill_key GROUP BY ds.skill_name ORDER BY 2 DESC LIMIT 20;`
- Remote distribution:
	- `SELECT dl.remote_type, COUNT(*) FROM fact_job_postings fp JOIN dim_location dl ON fp.location_key = dl.location_key GROUP BY dl.remote_type;`

**Resume bullet points**

- Built an end-to-end ETL pipeline that ingests job postings, extracts skills, and loads a dimensional warehouse supporting analytics and dashboards.
- Implemented idempotent dimension upserts and a many-to-many skills fact table for accurate skill demand analysis.
- Added a data quality framework producing JSON reports, visual artifacts, and Power BI-ready CSV exports.

**Interview questions & answers (brief)**

- Q: How do you ensure idempotency when loading dimensions? A: Use unique business keys and upserts (Postgres ON CONFLICT) for deterministic dimension inserts/updates.
- Q: How do you handle missing salary data? A: Compute coverage; skip misleading salary charts when coverage is low and surface a message in quality report.

---

If you'd like, I can also produce a one-page PDF slide (PNG snapshots + short narrative) suitable for LinkedIn or GitHub project featured images.

## Sample Insights

### Top Skills

![Top Skills](docs/releases/latest/screenshots/top_skills.png)

### Hiring by City

![City Distribution](docs/releases/latest/screenshots/city_distribution.png)

### Top Companies

![Top Companies](docs/releases/latest/screenshots/top_companies.png)
