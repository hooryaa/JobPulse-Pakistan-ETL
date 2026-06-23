"""Generate synthetic Rozee raw JSON and HTML files for pipeline testing.
Creates files under data/raw/rozee/<YYYYMMDD>/
"""
from pathlib import Path
import json
import hashlib
from datetime import datetime
import random

OUT_DIR = Path('data/raw/rozee') / datetime.utcnow().strftime('%Y%m%d')
HTML_DIR = OUT_DIR / 'html'
OUT_DIR.mkdir(parents=True, exist_ok=True)
HTML_DIR.mkdir(parents=True, exist_ok=True)

companies = [
    'NexaSoft', 'DataMinds', 'PakTech Solutions', 'Skyline Labs', 'Nimbus AI',
    'Habib Systems', 'GreenByte', 'Atlasware', 'Faisal Dynamics', 'Karachi Cloud'
]

cities = [
    'Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Faisalabad', 'Peshawar',
    'Quetta', 'Multan', 'Sialkot', 'Gujranwala'
]

roles = [
    'Software Engineer', 'Senior Backend Developer', 'Data Analyst', 'AI Engineer',
    'Frontend Developer', 'DevOps Engineer', 'QA Engineer', 'Product Manager',
    'HR Manager', 'Marketing Specialist'
]

skills_pool = [
    'Python', 'SQL', 'Pandas', 'Docker', 'Kubernetes', 'AWS', 'GCP', 'PostgreSQL',
    'JavaScript', 'React', 'Node.js', 'Spark', 'dbt', 'Power BI', 'ETL', 'Linux'
]

NUM = 120
for i in range(NUM):
    title = random.choice(roles)
    company = random.choice(companies)
    location = random.choice(cities)
    posting_id = str(900000 + i)
    url = f'https://www.rozee.pk/job/{posting_id}/{title.lower().replace(" ", "-")}'
    chosen_skills = random.sample(skills_pool, k=random.randint(2,5))
    salary_min = random.choice([30000, 50000, 70000, 100000])
    salary_max = salary_min + random.choice([20000, 30000, 50000])
    description = f"{title} at {company} based in {location}.\n\n"
    description += "Responsibilities:\n"
    description += "- " + "\n- ".join([
        f"Work on {random.choice(['backend systems', 'data pipelines', 'ML models', 'web frontends'])}" for _ in range(4)
    ]) + "\n\n"
    description += "Requirements:\n"
    description += "- " + "\n- ".join([f"{s} experience" for s in chosen_skills]) + "\n\n"
    description += "About the company:\n"
    description += (company + " is a fast-growing tech firm focused on delivering practical AI and data solutions. " * 3)

    content_hash = hashlib.sha1((title + company + description).encode('utf8')).hexdigest()
    job = {
        'posting_id': posting_id,
        'url': url,
        'title': title,
        'company': company,
        'location': location,
        'description': description,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_currency': 'PKR',
        'salary_period': 'monthly',
        'content_hash': content_hash,
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }

    json_path = OUT_DIR / f"{posting_id}.json"
    with open(json_path, 'w', encoding='utf8') as f:
        json.dump(job, f, ensure_ascii=False, indent=2)

    html_content = f"<html><head><title>{title} - {company}</title></head><body>"
    html_content += f"<h1>{title}</h1><div class='company'>{company}</div><div class='location'>{location}</div>"
    html_content += f"<div class='description'><h2>Responsibilities</h2><p>{' '.join(['Responsible for '+random.choice(['building systems','maintaining pipelines','developing features']) for _ in range(5)])}</p>"
    html_content += "<h2>Requirements</h2><ul>"
    for s in chosen_skills:
        html_content += f"<li>{s}</li>"
    html_content += "</ul></div></body></html>"
    html_path = HTML_DIR / f"{posting_id}.html"
    with open(html_path, 'w', encoding='utf8') as f:
        f.write(html_content)

print(f'Generated {NUM} synthetic Rozee raw files in {OUT_DIR}')
