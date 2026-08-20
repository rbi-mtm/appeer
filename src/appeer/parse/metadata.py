"""Canonical publication metadata and validation helpers."""

import datetime
import re


PUBLICATION_FIELDS = (
    'doi',
    'publisher',
    'journal',
    'title',
    'publication_type',
    'no_of_authors',
    'author_names',
    'affiliations',
    'received',
    'accepted',
    'published',
    'normalized_received',
    'normalized_accepted',
    'normalized_published',
    'normalized_publisher',
    'normalized_journal',
)

DOI_RE = re.compile(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', re.IGNORECASE)


def normalize_whitespace(value):
    """Collapse all Unicode whitespace in a string."""

    if not isinstance(value, str):
        return None
    normalized = ' '.join(value.split())
    return normalized or None


def normalize_doi(value):
    """Return a canonical lowercase DOI, or ``None`` for invalid syntax."""

    value = normalize_whitespace(value)
    if not value:
        return None

    lowered = value.lower()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'doi:'):
        if lowered.startswith(prefix):
            value = value[len(prefix):]
            break

    if not DOI_RE.fullmatch(value):
        return None
    return value.lower()


def is_iso_date(value):
    """Return whether *value* is a real ISO calendar date."""

    try:
        datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def normalize_known(value, index):
    """Normalize a publisher or journal through exact known variants."""

    candidate = normalize_whitespace(value)
    if not candidate:
        return None

    folded = candidate.casefold()
    for item in index.values():
        variants = item.get('name_variants', ())
        if any(normalize_whitespace(variant).casefold() == folded
               for variant in variants):
            return item['normalized_name']
    return None


def validate_metadata(metadata):
    """Return hard validation errors and non-fatal plausibility warnings."""

    invalid = []
    warnings = []

    for field in PUBLICATION_FIELDS:
        if metadata.get(field) in (None, '', [], ()):
            invalid.append(field)

    if metadata.get('doi') and not normalize_doi(metadata['doi']):
        invalid.append('doi')

    for field in ('normalized_received', 'normalized_accepted',
                  'normalized_published'):
        if metadata.get(field) and not is_iso_date(metadata[field]):
            invalid.append(field)

    authors = metadata.get('author_names')
    affiliations = metadata.get('affiliations')
    count = metadata.get('no_of_authors')
    if authors and (not isinstance(count, int) or count != len(authors)):
        invalid.append('no_of_authors')
    if authors and (not isinstance(affiliations, list)
                    or len(affiliations) != len(authors)
                    or not all(isinstance(entry, list) and entry
                               for entry in affiliations)):
        invalid.append('affiliations')

    received = metadata.get('normalized_received')
    accepted = metadata.get('normalized_accepted')
    published = metadata.get('normalized_published')
    if received and accepted and accepted < received:
        warnings.append('accepted_before_received')
    if received and published and published < received:
        warnings.append('published_before_received')
    if accepted and published and published < accepted:
        warnings.append('published_before_accepted')

    return sorted(set(invalid)), warnings
