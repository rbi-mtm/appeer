"""Stable structured metadata helpers used by supported publishers."""

import datetime
import json
import re

from appeer.parse.metadata import normalize_whitespace
from appeer.parse.parsers import date_utils


def meta_values(soup, *names):
    """Return nonempty meta contents matching names case-insensitively."""

    wanted = {name.casefold() for name in names}
    values = []
    for tag in soup.find_all('meta'):
        key = tag.get('name') or tag.get('property')
        value = normalize_whitespace(tag.get('content'))
        if key and key.casefold() in wanted and value:
            values.append(value)
    return values


def first_meta(soup, *names):
    values = meta_values(soup, *names)
    return values[0] if values else None


def scholarly_jsonld(soup):
    """Return the first JSON-LD ScholarlyArticle-like object."""

    candidates = []
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            candidates.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            candidates.append(data)

    for candidate in candidates:
        entity = candidate.get('mainEntity', candidate)
        entry_type = entity.get('@type', ())
        if isinstance(entry_type, str):
            entry_type = [entry_type]
        if any(kind in ('ScholarlyArticle', 'Article') for kind in entry_type):
            return entity
    return {}


def structured_authors(soup):
    """Return author names and per-author affiliations from JSON-LD."""

    names = []
    affiliations = []
    complete_affiliations = True
    for author in scholarly_jsonld(soup).get('author', ()):
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(author.get('name'))
        author_affiliations = []
        affiliation_data = author.get('affiliation', ())
        if isinstance(affiliation_data, dict):
            affiliation_data = [affiliation_data]
        for affiliation in affiliation_data:
            if isinstance(affiliation, str):
                value = normalize_whitespace(affiliation)
            elif isinstance(affiliation, dict):
                address = affiliation.get('address')
                if isinstance(address, dict):
                    value = normalize_whitespace(address.get('name'))
                else:
                    value = None
                value = value or normalize_whitespace(affiliation.get('name'))
            else:
                value = None
            if value and value not in author_affiliations:
                author_affiliations.append(value)
        if not name:
            continue
        if not author_affiliations:
            complete_affiliations = False
        names.append(name)
        affiliations.append(author_affiliations)
    if not names:
        return None, None
    return names, affiliations if complete_affiliations else None


def citation_authors(soup):
    """Read ordered citation authors and their following institutions."""

    names = []
    affiliations = []
    current = None
    for tag in soup.find_all('meta'):
        key = (tag.get('name') or '').casefold()
        value = normalize_whitespace(tag.get('content'))
        if key == 'citation_author' and value:
            names.append(value)
            affiliations.append([])
            current = affiliations[-1]
        elif key == 'citation_author_institution' and current is not None and value:
            if value not in current:
                current.append(value)
    if not names or not all(affiliations):
        return None, None
    return names, affiliations


def history_date(soup, label):
    """Extract a labelled received, accepted, or published date."""

    for item in soup.find_all(['li', 'div', 'p', 'span']):
        text = normalize_whitespace(item.get_text(' ', strip=True))
        if not text or not text.casefold().startswith(label.casefold()):
            continue
        time = item.find('time')
        if time and time.get('datetime'):
            return time['datetime'][:10]
        matches = date_utils.get_d_M_y(text)
        if matches:
            return matches[0]
    return None


def normalize_date(value):
    """Normalize either current publisher date representation to ISO."""

    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        return date_utils.normalize_d_M_y(value)


def labelled_date_in_text(soup, label):
    """Narrow fallback for RSC's inline article-history sentence."""

    pattern = re.compile(
        rf'{re.escape(label)}\s+(\d{{1,2}}(?:st|nd|rd|th)?\s+'
        rf'[A-Za-z]+\s+\d{{4}})',
        re.IGNORECASE,
    )
    match = pattern.search(soup.get_text(' ', strip=True))
    return normalize_whitespace(match.group(1)) if match else None
