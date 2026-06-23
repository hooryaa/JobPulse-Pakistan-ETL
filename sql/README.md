# SQL Views (metrics definitions)

This folder contains the canonical SQL definitions for the project's analytics
views. These views are the semantic layer (metrics contract) used by the
reporting layer and must be version-controlled.

Files
- `vw_top_skills.sql` — Returns the top skills with counts and normalized
  frequency. Columns: `skill`, `count`, `normalized_frequency`.
- `vw_city_demand.sql` — Returns job counts by `city`. Columns: `city`, `job_count`.
- `vw_company_activity.sql` — Returns job counts by `company_name`. Columns:
  `company_name`, `job_count`.

Metrics contract
- `top_skills` → `vw_top_skills`
- `city_demand` → `vw_city_demand`
- `company_activity` → `vw_company_activity`

Data quality thresholds
- Minimum total postings: 50
- Minimum skill coverage: 30% (postings with at least one extracted skill)

Expected outputs
- The pipeline produces timestamped reports under `reports/YYYY-MM-DD/`:
  - `weekly_report.md` — human-readable report
  - `insights_summary.json` — machine-readable metrics + data quality snapshot

Why these views
- Centralizing aggregation logic into SQL views ensures consistent metrics
  across scripts and simplifies downstream reporting and eventual dbt
  conversion.
