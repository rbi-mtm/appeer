"""Create a blinded first-pass eligibility screen from frozen sample titles."""

import argparse
import datetime as dt
from pathlib import Path
import re

from validation.scripts.common import VALIDATION_ROOT, read_csv, write_csv


FIELDS = [
    'doi', 'eligibility', 'exclusion_reason', 'classification_basis',
    'review_required', 'classified_at', 'notes',
]

EXCLUSION_PREFIXES = [
    ('author correction:', 'correction'),
    ('publisher correction:', 'correction'),
    ('correction:', 'correction'),
    ('correction to ', 'correction'),
    ('corrigendum', 'correction'),
    ('erratum:', 'correction'),
    ('retraction note:', 'retraction'),
    ('retracted:', 'retraction'),
    ('editorial board', 'editorial'),
    ('issue editorial masthead', 'editorial'),
    ('reply to ', 'comment_or_reply'),
    ('comment on ', 'comment_or_reply'),
]


def normalize_title(value):
    return ' '.join((value or '').split()).lower()


def classify(title):
    normalized = normalize_title(title)
    for prefix, reason in EXCLUSION_PREFIXES:
        if normalized.startswith(prefix):
            return 'ineligible', reason, f'title_prefix:{prefix}', 'no'
    if re.search(r'\b(systematic review|meta-analysis|meta analysis)\b',
                 normalized):
        return ('systematic_review', '', 'title_explicit_systematic_review',
                'yes')
    if (normalized.startswith('a review ') or normalized.endswith(': a review')
            or normalized.endswith('– a review')
            or normalized.endswith('- a review')):
        return 'ineligible', 'narrative_review', 'title_review_label', 'yes'
    if re.search(r'\b(a|the) perspective (on|of)\b', normalized):
        return 'ineligible', 'perspective', 'title_perspective_label', 'yes'
    return 'uncertain', '', 'publisher_article_type_required', 'yes'


def screen(args):
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = []
    for article in read_csv(args.sample):
        eligibility, reason, basis, review = classify(article['title'])
        rows.append({
            'doi': article['doi'],
            'eligibility': eligibility,
            'exclusion_reason': reason,
            'classification_basis': basis,
            'review_required': review,
            'classified_at': timestamp,
            'notes': (
                'Title-only screening is blinded to reference and appeer dates.'),
        })
    write_csv(args.output, FIELDS, rows)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        '--sample', type=Path,
        default=VALIDATION_ROOT / 'sampling' / 'sample.csv')
    result.add_argument(
        '--output', type=Path,
        default=VALIDATION_ROOT / 'adjudication' / 'eligibility.csv')
    return result


def main():
    screen(parser().parse_args())


if __name__ == '__main__':
    main()
