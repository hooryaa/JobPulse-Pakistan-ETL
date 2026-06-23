-- Remote vs Hybrid vs Onsite
SELECT dl.remote_flag, COUNT(*) AS postings
FROM dim_location dl
JOIN fact_job_postings f ON f.location_key = dl.location_key
GROUP BY dl.remote_flag
ORDER BY postings DESC;
-- Remote vs Hybrid vs Onsite
SELECT f.remote_type, COUNT(*) AS postings
FROM fact_job_postings f
GROUP BY f.remote_type;