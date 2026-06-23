-- Top hiring companies
SELECT dc.company_name, COUNT(*) AS postings
FROM dim_company dc
JOIN fact_job_postings f ON f.company_key = dc.company_key
GROUP BY dc.company_name
ORDER BY postings DESC
LIMIT 50;
-- Top hiring companies
SELECT company_name, COUNT(*) AS postings
FROM fact_job_postings
GROUP BY company_name
ORDER BY postings DESC
LIMIT 50;