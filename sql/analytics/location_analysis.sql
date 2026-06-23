-- Most active hiring locations
SELECT dl.country, dl.city, COUNT(*) AS postings
FROM dim_location dl
JOIN fact_job_postings f ON f.location_key = dl.location_key
GROUP BY dl.country, dl.city
ORDER BY postings DESC
LIMIT 50;
