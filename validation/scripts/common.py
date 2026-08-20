"""Shared validation-study utilities."""

import csv
import datetime as dt
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import time

import requests


VALIDATION_ROOT = Path(__file__).resolve().parents[1]
DOI_RE = re.compile(r'^10\.\d{4,9}/\S+$', re.IGNORECASE)


def load_json(path):
    """Load a UTF-8 JSON document."""

    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical_doi(value):
    """Return a canonical DOI or ``None`` for malformed input."""

    if not isinstance(value, str):
        return None
    value = value.strip()
    value = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value,
                   flags=re.IGNORECASE)
    value = re.sub(r'^doi:\s*', '', value, flags=re.IGNORECASE).strip()
    value = value.rstrip('.,;')
    if not DOI_RE.fullmatch(value) or any(char.isspace() for char in value):
        return None
    return value.lower()


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def deterministic_rank(seed, *parts):
    material = '\x1f'.join([seed, *(str(part) for part in parts)])
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


def iso_date(value):
    """Return a strict day-precision ISO date or ``None``."""

    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def crossref_date(value):
    """Normalize a Crossref date object and report its precision."""

    try:
        parts = value['date-parts'][0]
        if len(parts) == 3:
            normalized = dt.date(*parts).isoformat()
            return normalized, 'day'
        if len(parts) == 2:
            dt.date(parts[0], parts[1], 1)
            return f'{parts[0]:04d}-{parts[1]:02d}', 'month'
        if len(parts) == 1 and 1 <= parts[0] <= 9999:
            return f'{parts[0]:04d}', 'year'
    except (KeyError, TypeError, ValueError):
        pass
    return None, 'unknown'


def write_csv(path, fieldnames, rows):
    """Replace a CSV atomically."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames,
                                extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


class StudyClient:
    """Rate-limited HTTP client that records immutable source responses."""

    def __init__(self, user_agent, timeout=30, minimum_interval=0.34,
                 retries=3, session=None):
        configured = os.environ.get('APPEER_VALIDATION_USER_AGENT', user_agent)
        if 'replace-with-study-contact' in configured:
            raise ValueError(
                'Set APPEER_VALIDATION_USER_AGENT to a transparent user agent '
                'containing study contact information.')
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': configured})
        self._last_request = 0.0

    def get(self, url, *, params=None, headers=None):
        last_error = None
        for attempt in range(self.retries + 1):
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.minimum_interval:
                time.sleep(self.minimum_interval - elapsed)
            try:
                response = self.session.get(
                    url, params=params, headers=headers, timeout=self.timeout)
                self._last_request = time.monotonic()
            except requests.RequestException as error:
                last_error = error
                if attempt == self.retries:
                    raise
                time.sleep(min(2 ** attempt, 8))
                continue

            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            if attempt == self.retries:
                response.raise_for_status()
            time.sleep(self._retry_delay(response, attempt))
        raise last_error  # pragma: no cover

    @staticmethod
    def _retry_delay(response, attempt):
        value = response.headers.get('Retry-After')
        if value:
            try:
                return max(float(value), 0.0)
            except ValueError:
                parsed = email.utils.parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                now = dt.datetime.now(parsed.tzinfo)
                return max((parsed - now).total_seconds(), 0.0)
        return min(2 ** attempt, 8)

    @staticmethod
    def snapshot(response, source, identifier):
        """Store content by digest and return a provenance dictionary."""

        content = response.content
        digest = sha256_bytes(content)
        suffix = '.json' if 'json' in response.headers.get(
            'Content-Type', '').lower() else '.xml'
        directory = VALIDATION_ROOT / 'references' / 'raw' / source
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'{digest}{suffix}'
        if not path.exists():
            path.write_bytes(content)
        return {
            'source_record_id': identifier,
            'source_url': response.url,
            'retrieved_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'response_sha256': digest,
            'raw_path': str(path.relative_to(VALIDATION_ROOT)),
        }
