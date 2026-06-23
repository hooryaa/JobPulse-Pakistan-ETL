import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

import requests

LOGGER = logging.getLogger("jobpulse.extract")


class BaseConnector:
    def fetch(self, limit: int = 1000) -> List[Dict[str, Any]]:
        raise NotImplementedError()


class RemoteOKConnector(BaseConnector):
    def __init__(self, base_url: str = "https://remoteok.com/api", raw_dir: str = "data/raw"):
        self.base_url = base_url
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, limit: int = 1000) -> List[Dict[str, Any]]:
        # RemoteOK returns whole payload; we'll request once and filter
        url = self.base_url
        LOGGER.info("Fetching from RemoteOK: %s", url)
        attempts = 0
        while attempts < 3:
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                # RemoteOK returns a list where first element may be metadata
                jobs = [r for r in data if isinstance(r, dict) and r.get('id')]
                self._save_raw(jobs)
                LOGGER.info("Fetched %d records", len(jobs))
                return jobs[:limit]
            except Exception as e:
                attempts += 1
                LOGGER.warning("Fetch attempt %s failed: %s", attempts, e)
                time.sleep(2 ** attempts)
        LOGGER.error("Failed to fetch after retries")
        return []

    def _save_raw(self, payload: List[Dict[str, Any]]):
        ts = int(time.time())
        p = self.raw_dir / f"remoteok_raw_{ts}.json"
        with p.open("w", encoding="utf8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        LOGGER.debug("Saved raw payload to %s", p)


def get_connector(name: str = "remoteok", **kwargs) -> BaseConnector:
    if name == "remoteok":
        base = kwargs.get('base_url', 'https://remoteok.com/api')
        raw_dir = kwargs.get('raw_dir') or 'data/raw'
        return RemoteOKConnector(base, raw_dir)
    raise ValueError(f"Unknown connector: {name}")
import os
import time
import logging
from typing import List
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_URL = os.getenv("REMOTEOK_API_URL", "https://remoteok.com/api")


def fetch_remoteok_jobs(pages: int = 1, delay: float = 0.5) -> List[dict]:
    """Fetch job postings from RemoteOK API with simple retry and pagination support.

    Note: RemoteOK returns a single page in many cases; this function provides a
    reusable connector pattern and error handling.
    """
    results = []
    session = requests.Session()
    for page in range(1, pages + 1):
        url = API_URL
        params = {"page": page}
        attempts = 0
        while attempts < 3:
            try:
                r = session.get(url, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    results.extend(data)
                else:
                    logger.warning("Unexpected response format from API")
                break
            except requests.RequestException as e:
                attempts += 1
                logger.warning("Request failed (attempt %d): %s", attempts, e)
                time.sleep(2 ** attempts * delay)
        time.sleep(delay)
    logger.info("Fetched %d raw records", len(results))
    return results


def save_raw_json(records: List[dict], out_path: str) -> None:
    import json
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info("Saved raw JSON to %s", out_path)
