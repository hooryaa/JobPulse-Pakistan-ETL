-- Minimal schema for JobPulse
-- Star schema for JobPulse Data Warehouse (PostgreSQL)

CREATE TABLE IF NOT EXISTS dim_company (
  company_key SERIAL PRIMARY KEY,
  company_name TEXT NOT NULL UNIQUE,
  industry TEXT,
  company_size TEXT
);

CREATE INDEX IF NOT EXISTS idx_dim_company_name ON dim_company(company_name);

CREATE TABLE IF NOT EXISTS dim_location (
  location_key SERIAL PRIMARY KEY,
  country TEXT,
  state TEXT,
  city TEXT,
  remote_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_dim_location_city ON dim_location(city);

CREATE TABLE IF NOT EXISTS dim_skill (
  skill_key SERIAL PRIMARY KEY,
  skill_name TEXT NOT NULL UNIQUE,
  skill_category TEXT
);

CREATE INDEX IF NOT EXISTS idx_dim_skill_name ON dim_skill(skill_name);

CREATE TABLE IF NOT EXISTS dim_date (
  date_key SERIAL PRIMARY KEY,
  date DATE NOT NULL UNIQUE,
  day INT,
  month INT,
  quarter INT,
  year INT
);

CREATE INDEX IF NOT EXISTS idx_dim_date_ym ON dim_date(year, month);

CREATE TABLE IF NOT EXISTS dim_job (
  job_key SERIAL PRIMARY KEY,
  job_title TEXT NOT NULL,
  job_category TEXT,
  seniority_level TEXT
);

CREATE INDEX IF NOT EXISTS idx_dim_job_title ON dim_job(job_title);

-- Fact table: postings. posting_key is surrogate; posting_id stores source business key.
CREATE TABLE IF NOT EXISTS fact_job_postings (
  posting_key SERIAL PRIMARY KEY,
  posting_id TEXT NOT NULL UNIQUE,
  job_key INT NOT NULL REFERENCES dim_job(job_key),
  company_key INT NOT NULL REFERENCES dim_company(company_key),
  location_key INT NOT NULL REFERENCES dim_location(location_key),
  date_key INT NOT NULL REFERENCES dim_date(date_key),
  salary_min NUMERIC,
  salary_max NUMERIC,
  salary_avg NUMERIC,
  posting_count INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_fact_postings_jobkey ON fact_job_postings(job_key);
CREATE INDEX IF NOT EXISTS idx_fact_postings_companykey ON fact_job_postings(company_key);
CREATE INDEX IF NOT EXISTS idx_fact_postings_locationkey ON fact_job_postings(location_key);

-- Many-to-many: job postings <-> skills
CREATE TABLE IF NOT EXISTS fact_job_skills (
  id SERIAL PRIMARY KEY,
  posting_key INT NOT NULL REFERENCES fact_job_postings(posting_key) ON DELETE CASCADE,
  skill_key INT NOT NULL REFERENCES dim_skill(skill_key) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_fact_job_skills_posting_skill ON fact_job_skills(posting_key, skill_key);

