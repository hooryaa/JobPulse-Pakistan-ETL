-- Jobs posted by month
SELECT d.year, d.month, COUNT(*) AS jobs
FROM dim_date d
JOIN fact_job_postings f ON f.date_key = d.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;
-- Jobs posted by month
SELECT DATE_TRUNC('month', posted_at) AS month, COUNT(*) AS postings
FROM fact_job_postings
GROUP BY 1
ORDER BY 1;