# JobPulse — 2–3 Minute Recruiter Demo

This document is a short script and set of commands you can use to demo JobPulse to a recruiter, hiring manager, or interviewer. Focus on the workflow and the outputs — not the code.

Quick start (run the whole pipeline)

```bash
python run_pipeline.py
```

Interactive dashboard

```bash
streamlit run streamlit_app.py
```

What to show and say (2–3 minute script)

1) Raw data layer — immutable archive

```
ls -la data/raw/rozee/20260623/
```

Say:

> "This is the immutable raw layer. Every capture (JSON + html) is stored here for traceability and replay. We never edit raw files — transforms are repeatable from raw."

2) Transform / staging layer

```
ls -la data/staging/
cat data/staging/job_postings.csv | head -n 2
cat data/staging/job_skills.csv | head -n 2
```

Say:

> "The transform layer normalizes fields, parses salaries, extracts skills, and writes staging CSVs used to populate the warehouse. This is where cleaning and deterministic extraction happens."

3) Warehouse layer (SQL views)

Show the SQLite file:

```
ls -la data/warehouse/jobpulse.db
```

Run a quick SQL query (open `sqlite3` or use a GUI):

```sql
SELECT * FROM vw_top_skills LIMIT 10;
```

Say:

> "We expose analytics via SQL views (semantic layer) rather than ad-hoc Python code. Views like `vw_top_skills` and `vw_city_demand` are the canonical definitions of metrics used in reports."

4) Data Quality Gate

Open the generated insights file:

```
cat reports/latest/insights_summary.json | jq .data_quality
```

Example snippet that shows success:

```json
{
  "passed": true,
  "total_postings": 121,
  "postings_with_skills": 120,
  "skill_coverage_pct": 99.2,
  "top_skill": "TypeScript"
}
```

Say:

> "The pipeline runs a data-quality check before publishing reports. If thresholds (minimum postings, skill coverage) are not met, the pipeline marks the release as invalid and stops automatic insights."

5) Final outputs — release artifacts

Show the release directory:

```
ls -la releases/2026-06-23/
```

Open and present charts:

- `docs/releases/latest/screenshots/top_skills.png`
- `docs/releases/latest/screenshots/city_distribution.png`
- `docs/releases/latest/screenshots/top_companies.png`

Say:

> "The pipeline generates recruiter-ready visuals and a human-friendly `weekly_report.md` in the release folder. This can be emailed to stakeholders or used in a slide deck."

Demo talking points (quick bullets)

- Reproducible: `run_pipeline.py` runs the entire stack and packages a `releases/YYYY-MM-DD/` snapshot.
- Traceable: raw JSON and HTML are kept for replay and audit.
- Governed: data-quality checks prevent publishing low-quality insights.
- Semantic: views centralize metric definitions so analysts and dashboards share the same logic.

Architecture (one-slide ASCII)

```
             ┌──────────────┐
             │ Job Sources  │
             └──────┬───────┘
                    │
                    ▼
        ┌─────────────────────┐
        │ Raw Storage Layer   │
        │ JSON + HTML         │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ Transform Layer     │
        │ Cleaning            │
        │ Skill Extraction    │
        │ Normalization       │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ SQLite Warehouse    │
        │ Facts + Views       │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ Reporting Layer     │
        │ Charts + Insights   │
        └─────────────────────┘
```

Quick stat block (example to read aloud)

```
Pipeline Status: PASSED

Postings Processed: 121
Postings With Skills: 120
Skills Extracted: 520

DQ Gate: PASSED
Release Created: releases/2026-06-23/
```

Next steps to make this production-ready (one-liners)

- Move warehouse to Postgres and enable CI scheduled runs.
- Replace synthetic capture with live captures (Playwright or API) once infra is available.
- Add dbt for model lineage and tests.

Contact / Notes

Use `python run_pipeline.py` as the canonical execution path during interviews or demos. The rest of the repo contains implementation details for reviewers who want to dig in.
