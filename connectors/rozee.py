"""Simple Rozee.pk connector.

This connector is intentionally minimal: it fetches search result pages,
parses job detail links, fetches job pages, and writes raw JSON files to
data/raw/rozee/YYYYMMDD/<posting_id>.json for downstream processing.

Respect the site's ToS and rate limits. This is provided as a PoC.
"""
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse
import time
import json
import hashlib
from datetime import datetime
import re

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


def _safe_get(url, session=None, timeout=10):
    s = session or requests.Session()
    headers = {'User-Agent': USER_AGENT}
    try:
        r = s.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f'rozee: failed to GET {url}: {e}')
        return None


def _safe_get_search(url, timeout=30):
    """Fetch search pages using a headless browser to render JS.

    Falls back to `requests` if Playwright isn't installed or fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        # Playwright not available; fallback to requests
        return _safe_get(url, timeout=timeout)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f'rozee: playwright fetch failed for {url}: {e} — falling back to requests')
        return _safe_get(url, timeout=timeout)


def parse_search_listing(html):
    """Extract job detail links from Rozee search pages.

    Uses a stable pattern: /job/<numeric-id>/... and normalizes relative URLs.
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']

        # REAL Rozee job pattern (most stable)
        # /job/123456/job-title-slug
        if re.search(r'/job/\d+', href):
            # normalize relative -> absolute
            try:
                full_url = normalize_url(href)
            except Exception:
                full_url = None
            if full_url:
                links.append(full_url)

    # dedupe while preserving order
    seen = set()
    out = []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


BASE_URL = "https://www.rozee.pk"


def normalize_url(href: str) -> str:
    """Safely convert relative/absolute Rozee URLs into valid absolute URLs."""
    if not href:
        return None

    href = href.strip()

    # already absolute
    if href.startswith('http'):
        return href

    # fix double slashes or malformed relative paths
    return urljoin(BASE_URL, href)


def parse_job_detail(html, url):
    """Extract a minimal job dict from job page HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    # heuristics: title in h1, company in .company or similar
    title = None
    company = None
    desc = ''
    location = None
    salary_min = None
    salary_max = None
    salary_currency = None
    salary_period = None
    try:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
    except Exception:
        pass
    # company
    comp = soup.find(class_=re.compile('company|employer', re.I))
    if comp:
        company = comp.get_text(strip=True)
    # description
    desc_tag = soup.find(class_=re.compile('description|job-description|jobdesc', re.I))
    if desc_tag:
        desc = desc_tag.get_text('\n', strip=True)
    else:
        # fallback: collect paragraphs
        paras = [p.get_text(strip=True) for p in soup.find_all('p')]
        desc = '\n'.join(paras[:10])

    # posting id: use numeric id from URL when available to prevent duplicates
    match = re.search(r'/job/(\d+)', url)
    posting_id = match.group(1) if match else hashlib.sha1(url.encode('utf8')).hexdigest()

    # extract location heuristics
    loc_tag = soup.find(class_=re.compile('location|city|place', re.I))
    if loc_tag:
        location = loc_tag.get_text(' ', strip=True)

    # salary heuristics
    salary_text = ''
    sal_tag = soup.find(class_=re.compile('salary|compensation|package|pay', re.I))
    if sal_tag:
        salary_text = sal_tag.get_text(' ', strip=True)
    else:
        # search for currency-like patterns in the description
        if desc:
            m = re.search(r"(PKR|Rs\.?|Rs|USD|EUR|£|\$)\s*[\d,]+(?:\s*-\s*[\d,]+)?", desc, re.I)
            if m:
                salary_text = m.group(0)
    if salary_text:
        # simple normalization: capture numbers and possible range
        nums = re.findall(r"[\d,]+", salary_text)
        nums = [int(n.replace(',', '')) for n in nums]
        if nums:
            if len(nums) == 1:
                salary_min = salary_max = nums[0]
            else:
                salary_min, salary_max = nums[0], nums[-1]
        cur = re.search(r"(PKR|Rs\.?|Rs|USD|EUR|£|\$)", salary_text, re.I)
        if cur:
            salary_currency = cur.group(1)
        if '/month' in salary_text.lower() or 'per month' in salary_text.lower():
            salary_period = 'monthly'
        elif '/year' in salary_text.lower() or 'per year' in salary_text.lower() or '/yr' in salary_text.lower():
            salary_period = 'yearly'

    # content hash for dedupe detection
    content_hash = hashlib.sha1((str(title or '') + str(company or '') + str(desc)).encode('utf8')).hexdigest()

    return {
        'posting_id': posting_id,
        'url': url,
        'title': title,
        'company': company,
        'location': location,
        'description': desc,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_currency': salary_currency,
        'salary_period': salary_period,
        'content_hash': content_hash,
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }


def save_raw(jobdict, html=None, out_dir=Path('data/raw/rozee')):
    date_dir = out_dir / datetime.utcnow().strftime('%Y%m%d')
    html_dir = date_dir / 'html'
    date_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    path = date_dir / f"{jobdict['posting_id']}.json"
    with open(path, 'w', encoding='utf8') as f:
        json.dump(jobdict, f, ensure_ascii=False, indent=2)
    if html:
        html_path = html_dir / f"{jobdict['posting_id']}.html"
        with open(html_path, 'w', encoding='utf8') as f:
            f.write(html)
    return path


def fetch_search(url, max_items=20, delay=1.0):
    """Fetch a search page and return saved raw paths for job details.
    Example search URL: 'https://www.rozee.pk/job/jsearch/q/software-developer'
    """
    session = requests.Session()
    # Use a JS-capable fetch for search pages (Playwright). Falls back to requests.
    html = _safe_get_search(url, timeout=30)
    if not html:
        return []
    links = parse_search_listing(html)

    # safety: sometimes search pages return empty/blocked HTML
    if not links:
        print("rozee: no job links found (possible blocking or layout change)")
        return 0, []

    saved = []
    attempted = min(len(links), max_items)
    for link in links[:max_items]:
        time.sleep(delay)
        detail_html = _safe_get(link, session=session)
        if not detail_html:
            continue
        job = parse_job_detail(detail_html, link)
        # Data quality filter: only save meaningful postings
        desc = job.get('description') or ''
        title = job.get('title')
        html_ok = False
        # check HTML for common sections indicating a full job post
        if detail_html and re.search(r"Responsibilities|Requirements|Skills", detail_html, re.I):
            html_ok = True
        if title and (len(desc or '') > 200 or html_ok):
            p = save_raw(job, html=detail_html)
            saved.append(str(p))
        else:
            # skip saving low-quality capture
            continue
    return attempted, saved


if __name__ == '__main__':
    # simple demo: fetch a sample Rozee search (do not run without consent)
    # Correct Rozee search pattern
    # Example:
    # https://www.rozee.pk/job/jsearch/q/software-developer
    sample = "https://www.rozee.pk/job/jsearch/q/software-developer"
    print('Starting Rozee demo fetch (sample URL):', sample)
    out = fetch_search(sample, max_items=5, delay=1.5)
    print('Saved raw files:', out)