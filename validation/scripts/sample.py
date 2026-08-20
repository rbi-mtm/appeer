"""Build immutable DOI frames and deterministic validation samples."""

import argparse
import datetime as dt
import json
from pathlib import Path

from validation.scripts.common import (
    StudyClient,
    VALIDATION_ROOT,
    canonical_doi,
    deterministic_rank,
    load_json,
    sha256_bytes,
    write_csv,
)


SAMPLE_FIELDS = [
    'doi', 'publisher', 'journal', 'issn', 'year', 'cohort', 'split',
    'selection_rank', 'article_type', 'eligibility', 'exclusion_reason',
    'eligibility_source', 'eligibility_notes', 'oa_status', 'discipline',
    'author_count', 'citation_style', 'title', 'crossref_url',
]

RECONCILIATION_FIELDS = [
    'publisher', 'journal', 'issn', 'year', 'crossref_count',
    'publisher_archive_count', 'status', 'reviewer', 'reviewed_at', 'notes',
]


def frame_path(journal, year):
    name = f"{journal['publisher']}-{journal['issn']}-{year}.jsonl"
    return VALIDATION_ROOT / 'sampling' / 'frames' / name


def fetch_frame(client, journal, year, refresh=False):
    """Fetch a complete Crossref journal-year DOI frame."""

    path = frame_path(journal, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not refresh:
        with path.open(encoding='utf-8') as stream:
            count = sum(1 for line in stream if line.strip())
        return {
            'publisher': journal['publisher'],
            'journal': journal['journal'],
            'issn': journal['issn'],
            'year': year,
            'record_count': count,
            'sha256': sha256_bytes(path.read_bytes()),
            'path': str(path.relative_to(VALIDATION_ROOT)),
        }
    temporary = path.with_suffix('.jsonl.tmp')
    cursor = '*'
    seen = set()
    with temporary.open('w', encoding='utf-8') as stream:
        while cursor:
            response = client.get(
                f"https://api.crossref.org/journals/{journal['issn']}/works",
                params={
                    'filter': (
                        f'from-pub-date:{year}-01-01,'
                        f'until-pub-date:{year}-12-31,type:journal-article'),
                    'cursor': cursor,
                    'rows': 1000,
                    'select': ','.join([
                        'DOI', 'title', 'type', 'URL',
                        'published-online', 'published-print', 'issued',
                    ]),
                },
            )
            message = response.json()['message']
            added = 0
            for item in message.get('items', []):
                doi = canonical_doi(item.get('DOI'))
                if doi is None or doi in seen:
                    continue
                seen.add(doi)
                added += 1
                record = {
                    'doi': doi,
                    'publisher': journal['publisher'],
                    'journal': journal['journal'],
                    'issn': journal['issn'],
                    'year': year,
                    'title': ' '.join(item.get('title') or []),
                    'article_type': item.get('type'),
                    'crossref_url': item.get('URL'),
                }
                stream.write(json.dumps(record, sort_keys=True) + '\n')
            next_cursor = message.get('next-cursor')
            if not message.get('items', []):
                break
            if added == 0:
                raise ValueError(
                    f"Crossref cursor repeated a page for {journal['journal']} "
                    f'{year}; refusing to freeze an incomplete frame')
            if not next_cursor:
                raise ValueError(
                    f"Crossref omitted its next cursor for {journal['journal']} "
                    f'{year}; refusing to freeze an incomplete frame')
            cursor = next_cursor
    temporary.replace(path)
    return {
        'publisher': journal['publisher'],
        'journal': journal['journal'],
        'issn': journal['issn'],
        'year': year,
        'record_count': len(seen),
        'sha256': sha256_bytes(path.read_bytes()),
        'path': str(path.relative_to(VALIDATION_ROOT)),
    }


def fetch(args):
    study = load_json(args.study)
    journals = load_json(args.journals)
    client = StudyClient(
        study['user_agent'], study['request_timeout_seconds'],
        study['minimum_request_interval_seconds'])
    manifest = []
    for journal in journals:
        for year in study['years']:
            manifest.append(fetch_frame(client, journal, year, args.refresh))
    write_csv(
        VALIDATION_ROOT / 'sampling' / 'frame-manifest.csv',
        ['publisher', 'journal', 'issn', 'year', 'record_count', 'sha256',
         'path'],
        manifest,
    )
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    write_csv(
        VALIDATION_ROOT / 'sampling' / 'frame-reconciliation.csv',
        RECONCILIATION_FIELDS,
        [{
            'publisher': row['publisher'],
            'journal': row['journal'],
            'issn': row['issn'],
            'year': row['year'],
            'crossref_count': row['record_count'],
            'publisher_archive_count': '',
            'status': 'crossref_frame_frozen',
            'reviewer': 'automated_crossref_frame',
            'reviewed_at': retrieved_at,
            'notes': (
                'Complete Crossref ISSN/year journal-article query; publisher '
                'archive count not asserted.'),
        } for row in manifest],
    )


def ranked_frame(journal, year, seed):
    ranked = []
    with frame_path(journal, year).open(encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            record['selection_rank'] = deterministic_rank(
                seed, journal['publisher'], journal['issn'], year,
                record['doi'])
            ranked.append(record)
    return sorted(ranked, key=lambda item: item['selection_rank'])


def select(args):
    study = load_json(args.study)
    journals = load_json(args.journals)
    rows = []
    for journal in journals:
        for year in study['years']:
            ranked = ranked_frame(journal, year, study['seed'])
            random_count = study['population_random_per_cell']
            if len(ranked) < random_count:
                raise ValueError(
                    f"Insufficient frame for {journal['journal']} {year}: "
                    f'{len(ranked)} records')
            for index, row in enumerate(ranked[:random_count]):
                row['cohort'] = 'population_random'
                row['split'] = ('development' if index <
                                study['development_random_per_cell']
                                else 'holdout')
                rows.append(row)
    write_csv(args.output, SAMPLE_FIELDS, rows)
    manifest = {
        'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'protocol_version': study['protocol_version'],
        'seed': study['seed'],
        'article_count': len(rows),
        'development_count': sum(row['split'] == 'development' for row in rows),
        'holdout_count': sum(row['split'] == 'holdout' for row in rows),
        'sample_path': str(args.output.relative_to(VALIDATION_ROOT)),
        'sample_sha256': sha256_bytes(args.output.read_bytes()),
        'study_config_sha256': sha256_bytes(args.study.read_bytes()),
        'journal_config_sha256': sha256_bytes(args.journals.read_bytes()),
        'frame_manifest_sha256': sha256_bytes(
            (VALIDATION_ROOT / 'sampling' / 'frame-manifest.csv').read_bytes()),
    }
    manifest_path = args.output.with_name('sample-manifest.json')
    temporary = manifest_path.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(manifest_path)


def parser():
    root = VALIDATION_ROOT
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--study', type=Path,
                        default=root / 'config' / 'study.json')
    result.add_argument('--journals', type=Path,
                        default=root / 'config' / 'journals.json')
    subparsers = result.add_subparsers(required=True)
    fetch_parser = subparsers.add_parser('fetch')
    fetch_parser.add_argument('--refresh', action='store_true')
    fetch_parser.set_defaults(action=fetch)
    select_parser = subparsers.add_parser('select')
    select_parser.add_argument(
        '--output', type=Path,
        default=root / 'sampling' / 'sample.csv')
    select_parser.set_defaults(action=select)
    return result


def main():
    args = parser().parse_args()
    args.action(args)


if __name__ == '__main__':
    main()
