-- vw_company_activity: company_name, job_count
CREATE VIEW IF NOT EXISTS vw_company_activity AS
SELECT company AS company_name, COUNT(*) AS job_count
FROM staging_job_postings
GROUP BY company
ORDER BY job_count DESC;
