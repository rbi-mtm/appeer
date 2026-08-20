"""Verify frozen validation inputs and confirmatory dataset invariants."""

import argparse
from collections import Counter
import hashlib
from pathlib import Path

from validation.scripts.common import (
    VALIDATION_ROOT,
    canonical_doi,
    iso_date,
    load_json,
    read_csv,
)


TARGETS = {'received', 'accepted', 'published'}


def verify_configuration(study, journals):
    if len(journals) != 25:
        raise ValueError(f'Expected 25 journals, found {len(journals)}')
    if len({(row['publisher'], row['journal']) for row in journals}) != 25:
        raise ValueError('Publisher/journal pairs must be unique')
    if set(row['publisher'] for row in journals) != {
            'ACS', 'APS', 'ELS', 'NAT', 'RSC'}:
        raise ValueError('Configuration must cover all five publishers')
    if Counter(row['publisher'] for row in journals) != Counter({
            'ACS': 5, 'APS': 5, 'ELS': 5, 'NAT': 5, 'RSC': 5}):
        raise ValueError('Each publisher must contribute five journals')
    if study['years'] != [2021, 2022, 2023, 2024, 2025]:
        raise ValueError('The confirmatory years must remain 2021-2025')
    if study['population_random_per_cell'] != 7:
        raise ValueError('Random allocation changed from the protocol')
    if study['reference_enriched_per_cell'] != 3:
        raise ValueError('Enriched allocation changed from the protocol')


def verify_sample(rows, study):
    if len(rows) != 1250:
        raise ValueError(f'Expected 1,250 sampled articles, found {len(rows)}')
    dois = [canonical_doi(row['doi']) for row in rows]
    if None in dois or len(dois) != len(set(dois)):
        raise ValueError('Sample DOIs must be canonical and unique')
    cells = Counter((row['publisher'], row['issn'], row['year'], row['cohort'])
                    for row in rows)
    for publisher, issn, year, cohort in cells:
        expected = (study['population_random_per_cell']
                    if cohort == 'population_random'
                    else study['reference_enriched_per_cell'])
        if cells[(publisher, issn, year, cohort)] != expected:
            raise ValueError(f'Unbalanced cell: {publisher} {issn} {year} {cohort}')
    if len(cells) != 250:
        raise ValueError('Every journal-year must contain both cohorts')
    splits = Counter(row['split'] for row in rows)
    if splits != {'development': 500, 'holdout': 750}:
        raise ValueError(f'Unexpected split totals: {dict(splits)}')


def verify_reconciliation(rows):
    if len(rows) != 125:
        raise ValueError('Frame reconciliation requires one row per journal-year')
    keys = {(row['publisher'], row['issn'], row['year']) for row in rows}
    if len(keys) != 125:
        raise ValueError('Frame reconciliation journal-years must be unique')
    for row in rows:
        if row['status'] not in {'matched', 'explained_difference'}:
            raise ValueError(f"Unresolved frame reconciliation: {row['journal']} {row['year']}")
        if not row['reviewer'] or not row['reviewed_at']:
            raise ValueError('Every reconciliation requires reviewer provenance')


def verify_observations(rows):
    statuses = {
        'observed', 'source_not_covered', 'source_field_missing',
        'source_inaccessible', 'partial_precision', 'semantic_noncomparable',
        'source_conflict', 'malformed',
    }
    for row in rows:
        if canonical_doi(row['doi']) is None:
            raise ValueError(f"Invalid observation DOI: {row['doi']!r}")
        if row['target_field'] not in TARGETS or row['status'] not in statuses:
            raise ValueError(f'Invalid observation classification: {row}')
        if not row['source_lineage']:
            raise ValueError('Every observation requires a source lineage')
        if row['normalized_date'] and iso_date(row['normalized_date']) is None:
            raise ValueError(f"Invalid normalized date: {row['normalized_date']}")
        raw_path = row.get('raw_path')
        digest = row.get('response_sha256')
        if raw_path and digest:
            path = VALIDATION_ROOT / raw_path
            if not path.is_file():
                raise ValueError(f'Missing raw snapshot: {path}')
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            if observed != digest:
                raise ValueError(f'Raw snapshot digest mismatch: {path}')


def verify_final(sample, labels, appeer):
    sample_dois = {row['doi'] for row in sample}
    eligibility_values = {
        'original_research', 'review', 'methods', 'eligible', 'ineligible'}
    for row in sample:
        if row['eligibility'] not in eligibility_values:
            raise ValueError(f"Unclassified article eligibility: {row['doi']}")
        if not row['article_type']:
            raise ValueError(f"Missing article type: {row['doi']}")
    label_keys = {(row['doi'], row['target_field']) for row in labels}
    expected = {(doi, target) for doi in sample_dois for target in TARGETS}
    if label_keys != expected:
        raise ValueError('Final adjudication must contain exactly three rows per DOI')
    if {row['doi'] for row in appeer} != sample_dois:
        raise ValueError('Final appeer run must contain exactly one row per sampled DOI')
    for row in labels:
        if row['status'] == 'resolved':
            if row['confidence'] not in {'A', 'B', 'C'}:
                raise ValueError('Resolved labels require A, B, or C confidence')
            if iso_date(row['adjudicated_date']) is None:
                raise ValueError('Resolved labels require an exact date')
        elif row['status'] in {'genuinely_absent', 'truth_unresolved'}:
            if row['confidence'] != 'U' or row['adjudicated_date']:
                raise ValueError('Absent/unresolved labels require confidence U and no date')
        else:
            raise ValueError(f"Unknown adjudication status: {row['status']}")
        if not row['rationale'] or not row['adjudicator_primary']:
            raise ValueError('Every adjudication requires rationale and provenance')
        if row['confidence'] in {'A', 'B'} and not row['evidence_ids']:
            raise ValueError('A/B adjudications require evidence identifiers')
    provenance = ('parser', 'package_version', 'git_revision', 'input_sha256',
                  'parsed_at')
    for row in appeer:
        if canonical_doi(row['doi']) is None:
            raise ValueError(f"Invalid appeer-result DOI: {row['doi']}")
        if any(not row[field] for field in provenance):
            raise ValueError(f"Incomplete appeer provenance: {row['doi']}")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--stage', choices=['setup', 'sample', 'final'],
                        default='setup')
    return result


def main():
    args = parser().parse_args()
    study = load_json(VALIDATION_ROOT / 'config' / 'study.json')
    journals = load_json(VALIDATION_ROOT / 'config' / 'journals.json')
    verify_configuration(study, journals)
    if args.stage in {'sample', 'final'}:
        sample = read_csv(VALIDATION_ROOT / 'sampling' / 'sample.csv')
        verify_sample(sample, study)
        verify_reconciliation(read_csv(
            VALIDATION_ROOT / 'sampling' / 'frame-reconciliation.csv'))
        observations = read_csv(
            VALIDATION_ROOT / 'references' / 'observations.csv')
        verify_observations(observations)
    if args.stage == 'final':
        verify_final(
            sample,
            read_csv(VALIDATION_ROOT / 'adjudication' / 'labels.csv'),
            read_csv(VALIDATION_ROOT / 'runs' / 'appeer-results.csv'),
        )
    print(f'Validation {args.stage} checks passed.')


if __name__ == '__main__':
    main()
