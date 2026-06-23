-- vw_top_skills: skill, count, normalized_frequency
CREATE VIEW IF NOT EXISTS vw_top_skills AS
SELECT ds.skill_name AS skill, COUNT(*) AS count,
  ROUND(COUNT(*) * 1.0 / (SELECT COUNT(DISTINCT posting_key) FROM fact_job_skills), 4) AS normalized_frequency
FROM fact_job_skills fjs
JOIN dim_skill ds ON ds.skill_key = fjs.skill_key
GROUP BY ds.skill_name
ORDER BY count DESC;
