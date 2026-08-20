"""Stable structured metadata helpers used by supported publishers."""

import datetime
import html
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
            value = normalize_whitespace(re.sub(
                r'<[^>]+>', '', html.unescape(value)))
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
        match = explicit_date(text)
        if match:
            return match
    return None


def explicit_date(text):
    """Return an explicitly formatted calendar date from labelled text."""

    value = normalize_whitespace(text)
    if not value:
        return None

    iso_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', value)
    if iso_match:
        return iso_match.group()

    day_first = date_utils.get_d_M_y(value)
    if day_first:
        return day_first[0]

    months = '|'.join(date_utils._M_map()) # pylint: disable=protected-access
    month_first = re.search(
        rf'\b(?:{months})\s+\d{{1,2}},\s+\d{{4}}\b',
        value,
        re.IGNORECASE,
    )
    return month_first.group() if month_first else None


def normalize_date(value):
    """Normalize either current publisher date representation to ISO."""

    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        normalized = date_utils.normalize_d_M_y(value)
        if normalized:
            return normalized

    for date_format in ('%B %d, %Y', '%b %d, %Y'):
        try:
            return datetime.datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def assigned_json(soup, variable):
    """Load a JSON object assigned to a named JavaScript window variable."""

    marker = f'window.{variable}'
    decoder = json.JSONDecoder()
    for script in soup.find_all('script'):
        text = script.string or script.get_text()
        marker_index = text.find(marker)
        if marker_index < 0:
            continue
        equals_index = text.find('=', marker_index + len(marker))
        if equals_index < 0:
            continue
        candidate = text[equals_index + 1:].lstrip()
        try:
            value, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def science_direct_authors(author_data):
    """Read ScienceDirect's structured author-to-affiliation relationships."""

    if not isinstance(author_data, dict):
        return None, None

    affiliation_nodes = author_data.get('affiliations', {})
    affiliations_by_id = {}
    if isinstance(affiliation_nodes, dict):
        for identifier, node in affiliation_nodes.items():
            value = _science_direct_affiliation(node)
            if value:
                affiliations_by_id[identifier] = value

    authors = []
    author_affiliations = []
    content = author_data.get('content', ())
    for group in content if isinstance(content, list) else ():
        if not isinstance(group, dict) or group.get('#name') != 'author-group':
            continue
        for node in group.get('$$', ()):
            if not isinstance(node, dict) or node.get('#name') != 'author':
                continue
            children = node.get('$$', ())
            given = _science_direct_child_text(children, 'given-name')
            surname = _science_direct_child_text(children, 'surname')
            name = normalize_whitespace(' '.join(
                part for part in (given, surname) if part))
            references = []
            for child in children:
                if not isinstance(child, dict) or child.get('#name') != 'cross-ref':
                    continue
                reference = child.get('$', {}).get('refid')
                if reference in affiliations_by_id and reference not in references:
                    references.append(reference)
            if not references and len(affiliations_by_id) == 1:
                references = list(affiliations_by_id)
            if not name:
                continue
            authors.append(name)
            author_affiliations.append([
                affiliations_by_id[reference] for reference in references])

    if not authors:
        return None, None
    if not all(author_affiliations):
        return authors, None
    return authors, author_affiliations


def _science_direct_child_text(children, name):
    for child in children if isinstance(children, list) else ():
        if isinstance(child, dict) and child.get('#name') == name:
            return normalize_whitespace(child.get('_'))
    return None


def _science_direct_affiliation(node):
    if not isinstance(node, dict):
        return None
    children = node.get('$$', ())
    return (_science_direct_child_text(children, 'textfn')
            or _science_direct_child_text(children, 'source-text'))


def labelled_date_in_text(soup, label):
    """Narrow fallback for RSC's inline article-history sentence."""

    pattern = re.compile(
        rf'{re.escape(label)}\s+(\d{{1,2}}(?:st|nd|rd|th)?\s+'
        rf'[A-Za-z]+\s+\d{{4}})',
        re.IGNORECASE,
    )
    match = pattern.search(soup.get_text(' ', strip=True))
    return normalize_whitespace(match.group(1)) if match else None
