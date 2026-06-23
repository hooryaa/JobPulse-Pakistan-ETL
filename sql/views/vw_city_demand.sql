-- vw_city_demand: city, job_count
CREATE VIEW IF NOT EXISTS vw_city_demand AS
SELECT city, COUNT(*) AS job_count
FROM staging_job_postings
GROUP BY city
ORDER BY job_count DESC;
