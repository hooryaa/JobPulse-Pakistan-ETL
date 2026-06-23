-- Top 20 most requested skills
SELECT skill_name, COUNT(*) AS requests
FROM dim_skill ds
JOIN fact_job_postings f ON ds.skill_key = f.posting_key
GROUP BY skill_name
ORDER BY requests DESC
LIMIT 20;
-- Top 20 most requested skills
SELECT skill_name, COUNT(*) AS mentions
FROM dim_skill s
JOIN fact_job_postings f ON POSITION(LOWER(s.skill_name) IN LOWER(f.job_title)) > 0 OR POSITION(LOWER(s.skill_name) IN LOWER(f.company_name)) > 0
GROUP BY skill_name
ORDER BY mentions DESC
LIMIT 20;