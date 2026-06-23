import unicodedata
import re
from typing import Optional


def clean_text(s: Optional[str]) -> Optional[str]:
    """Normalize Unicode, strip control characters, and collapse whitespace.

    Returns None for empty input.
    """
    if s is None:
        return None
    try:
        # Ensure it's a str
        if not isinstance(s, str):
            s = str(s)
        # Attempt to repair common mojibake (latin-1 / utf-8 confusion)
        def _score_candidate(txt: str) -> int:
            # higher is better: count of printable letter/number characters
            return sum(1 for ch in txt if ch.isalnum() or ch.isspace())

        candidates = [s]
        try:
            candidates.append(s.encode('latin-1', errors='replace').decode('utf-8', errors='replace'))
        except Exception:
            pass
        try:
            candidates.append(s.encode('utf-8', errors='replace').decode('latin-1', errors='replace'))
        except Exception:
            pass
        # pick best candidate by printable score
        best = max(candidates, key=_score_candidate)
        s = best
        # Normalize unicode to composed form
        s = unicodedata.normalize('NFKC', s)
        # Remove replacement characters and other control noise
        s = re.sub(r"[\x00-\x1F\x7F]+", ' ', s)
        # Collapse multiple whitespace
        s = re.sub(r"\s+", ' ', s).strip()
        if s == '':
            return None
        return s
    except Exception:
        try:
            return str(s)
        except Exception:
            return None
