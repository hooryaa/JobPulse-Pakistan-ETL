-- Highest paying skill categories (simplified)
SELECT ds.skill_category, AVG(f.salary_avg) AS avg_salary
FROM dim_skill ds
JOIN fact_job_postings f ON ds.skill_key = f.posting_key
GROUP BY ds.skill_category
ORDER BY avg_salary DESC
LIMIT 20;
