"""Produce automated reference comparisons and a blinded adjudication queue."""

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path

from validation.scripts.common import (
    VALIDATION_ROOT, iso_date, read_csv, sha256_bytes, write_csv)


COMPARISON_FIELDS = [
    'doi', 'publisher', 'journal', 'split', 'target_field',
    'reference_status', 'reference_date', 'reference_dates',
    'evidence_sources', 'evidence_lineages', 'appeer_date',
    'comparison_status', 'difference_days',
]

QUEUE_FIELDS = [
    'doi', 'publisher', 'journal', 'split', 'eligibility', 'reasons',
    'received_reference_status', 'accepted_reference_status',
    'published_reference_status', 'blinded_to_appeer',
]

COMPARABLE_PUBLISHED = {
    'accepted_manuscript', 'ahead_of_print', 'published_online',
    'available_online', 'first_published', 'version_of_record',
}


def observed(rows, target):
    result = []
    for row in rows:
        if row['target_field'] != target or row['status'] != 'observed':
            continue
        if row.get('explicit_or_inferred') != 'explicit':
            continue
        value = iso_date(row.get('normalized_date', ''))
        if not value:
            continue
        if target == 'published' and row.get('semantic_concept') not in (
                COMPARABLE_PUBLISHED):
            continue
        result.append((value, row['source'], row['source_lineage']))
    return result


def reference_summary(rows, target):
    evidence = observed(rows, target)
    dates = sorted({value for value, source, lineage in evidence})
    sources = sorted({source for value, source, lineage in evidence})
    lineages = sorted({lineage for value, source, lineage in evidence})
    if not dates:
        status = 'reference_unavailable'
        reference = ''
    elif len(dates) == 1:
        status = ('multi_source_agreement' if len(sources) > 1
                  else 'single_source_date')
        reference = dates[0]
    else:
        status = 'source_disagreement'
        reference = ''
    return {
        'status': status,
        'date': reference,
        'dates': '|'.join(dates),
        'sources': '|'.join(sources),
        'lineages': '|'.join(lineages),
    }


def compare(reference, appeer_value, appeer_ran):
    if not appeer_ran:
        return 'appeer_not_run', ''
    actual = iso_date(appeer_value or '')
    expected = iso_date(reference['date']) if reference['date'] else None
    if expected is None:
        return ('reference_disagreement' if reference['status'] ==
                'source_disagreement' else 'reference_unavailable'), ''
    if actual is None:
        return 'appeer_missing_reference_exists', ''
    delta = (dt.date.fromisoformat(actual) -
             dt.date.fromisoformat(expected)).days
    return ('exact' if delta == 0 else 'different'), str(delta)


def generate(args):
    sample = read_csv(args.sample)
    observations = read_csv(args.observations)
    eligibility = {row['doi']: row for row in read_csv(args.eligibility)}
    by_doi = defaultdict(list)
    for row in observations:
        by_doi[row['doi']].append(row)

    appeer_rows = read_csv(args.appeer) if args.appeer.exists() else []
    appeer = {row['doi']: row for row in appeer_rows}
    appeer_ran = bool(appeer_rows)
    comparisons = []
    queue = []
    source_counts = defaultdict(Counter)
    evidence_counts = defaultdict(Counter)
    disagreement_counts = Counter()
    complete_evidence = Counter()

    for article in sample:
        doi = article['doi']
        doi_rows = by_doi.get(doi, [])
        statuses = {}
        reasons = []
        found_all = True
        for target in ('received', 'accepted', 'published'):
            reference = reference_summary(doi_rows, target)
            statuses[target] = reference['status']
            if not reference['date']:
                found_all = False
            if reference['status'] == 'source_disagreement':
                disagreement_counts[(article['publisher'], target)] += 1
                reasons.append(f'{target}:source_disagreement')
            if reference['status'] == 'reference_unavailable':
                reasons.append(f'{target}:reference_unavailable')
            comparison, difference = compare(
                reference, appeer.get(doi, {}).get(target, ''), appeer_ran)
            if comparison in {'different', 'appeer_missing_reference_exists'}:
                reasons.append(f'{target}:{comparison}')
            comparisons.append({
                'doi': doi, 'publisher': article['publisher'],
                'journal': article['journal'], 'split': article['split'],
                'target_field': target,
                'reference_status': reference['status'],
                'reference_date': reference['date'],
                'reference_dates': reference['dates'],
                'evidence_sources': reference['sources'],
                'evidence_lineages': reference['lineages'],
                'appeer_date': appeer.get(doi, {}).get(target, ''),
                'comparison_status': comparison,
                'difference_days': difference,
            })
            if reference['date']:
                evidence_counts[(article['publisher'], target)]['articles'] += 1
        if found_all:
            complete_evidence[article['publisher']] += 1

        eligibility_row = eligibility.get(doi, {})
        if eligibility_row.get('review_required', 'yes') == 'yes':
            reasons.append('eligibility:manual_review')
        if reasons:
            queue.append({
                'doi': doi, 'publisher': article['publisher'],
                'journal': article['journal'], 'split': article['split'],
                'eligibility': eligibility_row.get('eligibility', 'uncertain'),
                'reasons': '|'.join(sorted(set(reasons))),
                'received_reference_status': statuses['received'],
                'accepted_reference_status': statuses['accepted'],
                'published_reference_status': statuses['published'],
                'blinded_to_appeer': 'yes' if not appeer_ran else 'no',
            })

        for source in ('crossref', 'pubmed', 'europe_pmc', 'pmc_jats'):
            source_rows = [row for row in doi_rows if row['source'] == source]
            counter = source_counts[(article['publisher'], source)]
            counter['sampled'] += 1
            if not source_rows:
                counter['not_attempted'] += 1
            elif any(row['status'] == 'source_inaccessible'
                     for row in source_rows):
                counter['inaccessible'] += 1
            else:
                counter['harvest_success'] += 1
                if any(row['status'] != 'source_not_covered'
                       for row in source_rows):
                    counter['covered'] += 1

    write_csv(args.comparisons, COMPARISON_FIELDS, comparisons)
    write_csv(args.queue, QUEUE_FIELDS, queue)
    availability_rows = []
    for (publisher, source), counter in sorted(source_counts.items()):
        availability_rows.append({
            'publisher': publisher, 'source': source,
            **{key: counter[key] for key in (
                'sampled', 'harvest_success', 'covered', 'inaccessible',
                'not_attempted')},
        })
    write_csv(args.availability, [
        'publisher', 'source', 'sampled', 'harvest_success', 'covered',
        'inaccessible', 'not_attempted'], availability_rows)

    summary = {
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'sample_articles': len(sample),
        'observations': len(observations),
        'appeer_run_available': appeer_ran,
        'manual_queue_articles': len(queue),
        'reference_evidence': {
            publisher: {
                target: evidence_counts[(publisher, target)]['articles']
                for target in ('received', 'accepted', 'published')
            } for publisher in ('NAT', 'RSC', 'ACS', 'APS', 'ELS')
        },
        'complete_lifecycle_evidence': {
            publisher: complete_evidence[publisher]
            for publisher in ('NAT', 'RSC', 'ACS', 'APS', 'ELS')
        },
        'source_disagreements': {
            publisher: {
                target: disagreement_counts[(publisher, target)]
                for target in ('received', 'accepted', 'published')
            } for publisher in ('NAT', 'RSC', 'ACS', 'APS', 'ELS')
        },
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.summary.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n',
                         encoding='utf-8')
    temporary.replace(args.summary)
    files = [args.comparisons, args.queue, args.availability, args.summary]
    manifest = [{
        'path': str(path.relative_to(VALIDATION_ROOT)),
        'sha256': sha256_bytes(path.read_bytes()),
    } for path in files]
    write_csv(args.manifest, ['path', 'sha256'], manifest)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--sample', type=Path,
                        default=VALIDATION_ROOT / 'sampling' / 'sample.csv')
    result.add_argument('--observations', type=Path,
                        default=VALIDATION_ROOT / 'references' / 'observations.csv')
    result.add_argument('--eligibility', type=Path,
                        default=VALIDATION_ROOT / 'adjudication' / 'eligibility.csv')
    result.add_argument('--appeer', type=Path,
                        default=VALIDATION_ROOT / 'runs' / 'appeer-results.csv')
    result.add_argument('--comparisons', type=Path,
                        default=VALIDATION_ROOT / 'reports' / 'comparisons.csv')
    result.add_argument('--queue', type=Path,
                        default=VALIDATION_ROOT / 'adjudication' / 'manual-queue.csv')
    result.add_argument('--availability', type=Path,
                        default=VALIDATION_ROOT / 'reports' / 'harvest-availability.csv')
    result.add_argument('--summary', type=Path,
                        default=VALIDATION_ROOT / 'reports' / 'pre-adjudication.json')
    result.add_argument('--manifest', type=Path,
                        default=VALIDATION_ROOT / 'reports' / 'manifest.csv')
    return result


def main():
    generate(parser().parse_args())


if __name__ == '__main__':
    main()
