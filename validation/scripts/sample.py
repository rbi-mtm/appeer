"""Build immutable DOI frames and deterministic validation samples."""

import argparse
import json
from pathlib import Path

from validation.scripts.common import (
    StudyClient,
    VALIDATION_ROOT,
    canonical_doi,
    deterministic_rank,
    load_json,
    read_csv,
    sha256_bytes,
    write_csv,
)


SAMPLE_FIELDS = [
    'doi', 'publisher', 'journal', 'issn', 'year', 'cohort', 'split',
    'selection_rank', 'article_type', 'eligibility', 'oa_status', 'discipline',
    'author_count', 'citation_style', 'title', 'crossref_url',
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
            for item in message.get('items', []):
                doi = canonical_doi(item.get('DOI'))
                if doi is None or doi in seen:
                    continue
                seen.add(doi)
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
            if not message.get('items', []) or next_cursor == cursor:
                break
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
            reserve_count = study['candidate_reserve_per_cell']
            if len(ranked) < random_count + reserve_count:
                raise ValueError(
                    f"Insufficient frame for {journal['journal']} {year}: "
                    f'{len(ranked)} records')
            for index, row in enumerate(ranked[:random_count]):
                row['cohort'] = 'population_random'
                row['split'] = ('development' if index <
                                study['development_random_per_cell']
                                else 'holdout')
                rows.append(row)
            for row in ranked[random_count:random_count + reserve_count]:
                row['cohort'] = 'reference_candidate'
                row['split'] = 'unassigned'
                rows.append(row)
    write_csv(args.output, SAMPLE_FIELDS, rows)


def finalize(args):
    study = load_json(args.study)
    rows = read_csv(args.candidates)
    observations = read_csv(args.observations)
    explicit = set()
    for observation in observations:
        if (observation['status'] == 'observed'
                and observation['explicit_or_inferred'] == 'explicit'
                and observation['target_field'] in {'received', 'accepted'}
                and observation['precision'] == 'day'):
            explicit.add(observation['doi'])

    final_rows = [row for row in rows
                  if row['cohort'] == 'population_random']
    groups = {}
    for row in rows:
        if row['cohort'] != 'reference_candidate' or row['doi'] not in explicit:
            continue
        groups.setdefault((row['publisher'], row['issn'], row['year']), []).append(row)

    required = study['reference_enriched_per_cell']
    development = study['development_enriched_per_cell']
    expected_groups = len(load_json(args.journals)) * len(study['years'])
    if len(groups) != expected_groups:
        raise ValueError(
            'At least one journal-year has no explicit lifecycle candidates; '
            'inspect source coverage before changing the sample.')
    for key, candidates in groups.items():
        chosen = sorted(candidates, key=lambda item: item['selection_rank'])[:required]
        if len(chosen) < required:
            raise ValueError(f'Only {len(chosen)} enriched candidates for {key}')
        for index, row in enumerate(chosen):
            row['cohort'] = 'reference_enriched'
            row['split'] = 'development' if index < development else 'holdout'
            final_rows.append(row)

    final_rows.sort(key=lambda row: (
        row['publisher'], row['journal'], row['year'], row['cohort'],
        row['selection_rank']))
    write_csv(args.output, SAMPLE_FIELDS, final_rows)


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
        default=root / 'sampling' / 'candidate-sample.csv')
    select_parser.set_defaults(action=select)
    finalize_parser = subparsers.add_parser('finalize')
    finalize_parser.add_argument(
        '--candidates', type=Path,
        default=root / 'sampling' / 'candidate-sample.csv')
    finalize_parser.add_argument(
        '--observations', type=Path,
        default=root / 'references' / 'observations.csv')
    finalize_parser.add_argument(
        '--output', type=Path,
        default=root / 'sampling' / 'sample.csv')
    finalize_parser.set_defaults(action=finalize)
    return result


def main():
    args = parser().parse_args()
    args.action(args)


if __name__ == '__main__':
    main()
