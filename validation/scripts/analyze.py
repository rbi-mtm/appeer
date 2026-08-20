"""Calculate accuracy, coverage, interval, and missingness results."""

import argparse
from collections import defaultdict
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np

from validation.scripts.common import VALIDATION_ROOT, read_csv


TARGETS = ('received', 'accepted', 'published')


def wilson_interval(successes, total, z=1.959963984540054):
    """Return a two-sided Wilson score interval."""

    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    lower = 0.0 if successes == 0 else max(0.0, centre - margin)
    upper = 1.0 if successes == total else min(1.0, centre + margin)
    return [lower, upper]


def parse_day(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def rate(numerator, denominator):
    return {
        'numerator': numerator,
        'denominator': denominator,
        'value': numerator / denominator if denominator else None,
        'wilson_95': wilson_interval(numerator, denominator),
    }


def median(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def percentile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def describe(values):
    return {
        'n': len(values),
        'median': median(values),
        'iqr': [percentile(values, 0.25), percentile(values, 0.75)],
        'p10': percentile(values, 0.10),
        'p90': percentile(values, 0.90),
    }


def weighted_percentile(values, weights, probability):
    if not values:
        return None
    ordered = sorted(zip(values, weights), key=lambda pair: pair[0])
    total = sum(weight for _, weight in ordered)
    if total <= 0:
        return None
    threshold = probability * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def completion_propensities(records):
    """Estimate additive completeness propensities with regularized logistic IRLS."""

    if not records:
        return {}
    dimensions = ('publisher', 'journal', 'year', 'article_type', 'oa_status')
    categories = {
        dimension: sorted({str(record.get(dimension) or 'unknown')
                           for record in records})
        for dimension in dimensions
    }
    columns = [('intercept', '')]
    for dimension in dimensions:
        columns.extend((dimension, value)
                       for value in categories[dimension][1:])
    matrix = []
    outcomes = []
    for record in records:
        row = [1.0]
        for dimension, value in columns[1:]:
            row.append(float(str(record.get(dimension) or 'unknown') == value))
        matrix.append(row)
        outcomes.append(float(record['_complete']))
    design = np.asarray(matrix, dtype=float)
    outcome = np.asarray(outcomes, dtype=float)
    if np.all(outcome == outcome[0]):
        probability = min(max(float(outcome[0]), 0.01), 0.99)
        return {record['doi']: probability for record in records}
    beta = np.zeros(design.shape[1])
    penalty = np.eye(design.shape[1]) * 1e-6
    penalty[0, 0] = 0
    for _ in range(50):
        linear = np.clip(design @ beta, -30, 30)
        predicted = 1 / (1 + np.exp(-linear))
        weights = np.clip(predicted * (1 - predicted), 1e-8, None)
        hessian = design.T @ (weights[:, None] * design) + penalty
        gradient = design.T @ (outcome - predicted) - penalty @ beta
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    predicted = 1 / (1 + np.exp(-np.clip(design @ beta, -30, 30)))
    predicted = np.clip(predicted, 0.05, 0.995)
    return {record['doi']: float(value)
            for record, value in zip(records, predicted)}


def selection_bias(selected, appeer, truths):
    records = []
    for doi, article in selected.items():
        if article['cohort'] != 'population_random' or not eligible(article):
            continue
        output = appeer.get(doi, {})
        record = dict(article)
        record['doi'] = doi
        record['_complete'] = all(parse_day(output.get(target))
                                  for target in TARGETS)
        records.append(record)
    propensities = completion_propensities(records)
    result = {}
    for name, start, end in (
            ('review_days', 'received', 'accepted'),
            ('post_acceptance_days', 'accepted', 'published')):
        all_truth = []
        complete_truth = []
        complete_weights = []
        for record in records:
            first = truths.get((record['doi'], start))
            second = truths.get((record['doi'], end))
            if not first or not second:
                continue
            if (first['status'] != 'resolved' or second['status'] != 'resolved'
                    or first['confidence'] not in {'A', 'B'}
                    or second['confidence'] not in {'A', 'B'}):
                continue
            first_date = parse_day(first['adjudicated_date'])
            second_date = parse_day(second['adjudicated_date'])
            value = (second_date - first_date).days
            all_truth.append(value)
            if record['_complete']:
                complete_truth.append(value)
                complete_weights.append(1 / propensities[record['doi']])
        complete_median = median(complete_truth)
        weighted_median = weighted_percentile(
            complete_truth, complete_weights, 0.5)
        all_description = describe(all_truth)
        iqr = all_description['iqr']
        iqr_width = (iqr[1] - iqr[0]) if all_truth else None
        threshold = max(3, 0.1 * iqr_width) if iqr_width is not None else None
        shift = (weighted_median - complete_median
                 if weighted_median is not None and complete_median is not None
                 else None)
        result[name] = {
            'all_adjudicated': all_description,
            'complete_case': describe(complete_truth),
            'ipw_median': weighted_median,
            'ipw_shift_from_complete_median': shift,
            'selection_sensitive': (
                abs(shift) > threshold if shift is not None else None),
            'sensitivity_threshold_days': threshold,
        }
    return result


def index_unique(rows, name):
    result = {}
    for row in rows:
        key = row['doi'].lower()
        if key in result:
            raise ValueError(f'Duplicate DOI in {name}: {key}')
        result[key] = row
    return result


def truth_index(rows):
    result = {}
    for row in rows:
        key = (row['doi'].lower(), row['target_field'])
        if key in result:
            raise ValueError(f'Duplicate adjudication: {key}')
        result[key] = row
    return result


def eligible(row):
    return row.get('eligibility', '').lower() in {
        'eligible', 'original_research', 'methods', 'systematic_review',
        'registered_report'}


def accuracy_category(actual, expected):
    difference = (actual - expected).days
    absolute = abs(difference)
    if absolute == 0:
        category = 'exact'
    elif absolute == 1:
        category = 'within_one_day'
    elif absolute <= 7:
        category = 'two_to_seven_days'
    else:
        category = 'greater_than_seven_days'
    return difference, category


def calculate(sample_rows, adjudication_rows, appeer_rows, split='holdout',
              discrepancy_rows=None):
    samples = index_unique(sample_rows, 'sample')
    appeer = index_unique(appeer_rows, 'appeer results')
    truths = truth_index(adjudication_rows)
    selected = {
        doi: article for doi, article in samples.items()
        if article['split'] == split
    }
    result = {
        'split': split,
        'article_count': len(selected),
        'targets': {},
        'whole_record': {},
        'intervals': {},
        'missingness': {},
        'selection_bias': {},
        'publisher_verdicts': {},
        'pooled_verdicts': {},
        'operational_verdict': {},
    }
    discrepancy_rows = discrepancy_rows or []
    critical_dois = {
        row['doi'].lower() for row in discrepancy_rows
        if row.get('severity') == 'critical'
        and row.get('doi', '').lower() in selected
    }

    per_target_publisher = defaultdict(lambda: defaultdict(
        lambda: defaultdict(int)))
    per_target_publisher_journal = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int)))
    exact_triplets = complete_triplets = triplet_truth = 0
    interval_errors = {'review_days': [], 'post_acceptance_days': []}
    interval_truth = {'review_days': [], 'post_acceptance_days': []}

    for target in TARGETS:
        counts = defaultdict(int)
        for doi, article in selected.items():
            output = appeer.get(doi, {})
            actual = parse_day(output.get(target))
            truth = truths.get((doi, target))
            is_random_eligible = (
                article['cohort'] == 'population_random' and eligible(article))
            if is_random_eligible:
                counts['coverage_denominator'] += 1
                if actual:
                    counts['extracted'] += 1
            if truth and truth['status'] == 'resolved' and truth['confidence'] in {'A', 'B'}:
                expected = parse_day(truth['adjudicated_date'])
                if expected is None:
                    raise ValueError(f'Invalid adjudicated date for {doi} {target}')
                counts['reference_available'] += 1
                publisher_counts = per_target_publisher[target][article['publisher']]
                publisher_counts['reference_available'] += 1
                per_target_publisher_journal[target][article['publisher']][
                    article['journal']] += 1
                if actual is None:
                    counts['appeer_missing'] += 1
                    publisher_counts['appeer_missing'] += 1
                    continue
                counts['returned_evaluable'] += 1
                publisher_counts['returned_evaluable'] += 1
                difference, category = accuracy_category(actual, expected)
                counts[category] += 1
                publisher_counts[category] += 1
                if abs(difference) > 1:
                    counts['silent_wrong'] += 1
                    publisher_counts['silent_wrong'] += 1
        result['targets'][target] = {
            'reference_available': counts['reference_available'],
            'coverage': rate(counts['extracted'], counts['coverage_denominator']),
            'omission': rate(counts['appeer_missing'], counts['reference_available']),
            'exact': rate(counts['exact'], counts['returned_evaluable']),
            'exact_or_one_day': rate(
                counts['exact'] + counts['within_one_day'],
                counts['returned_evaluable']),
            'two_to_seven_days': counts['two_to_seven_days'],
            'greater_than_seven_days': counts['greater_than_seven_days'],
            'silent_wrong': rate(
                counts['silent_wrong'], counts['returned_evaluable']),
        }
        silent_rate = result['targets'][target]['silent_wrong']
        exact_rate = result['targets'][target]['exact']
        exact_one_rate = result['targets'][target]['exact_or_one_day']
        silent_upper = (wilson_interval(
            silent_rate['numerator'], silent_rate['denominator'],
            z=1.6448536269514722) or [None, None])[1]
        if counts['reference_available'] < 400:
            pooled_verdict = 'insufficient_evidence'
        elif (silent_rate['value'] is not None
              and silent_rate['value'] <= 0.005
              and silent_upper <= 0.03
              and exact_rate['value'] >= 0.98
              and exact_one_rate['value'] >= 0.99
              and not critical_dois):
            pooled_verdict = 'date_accuracy_validated'
        else:
            pooled_verdict = 'failed_accuracy_threshold'
        result['pooled_verdicts'][target] = {
            'verdict': pooled_verdict,
            'silent_wrong_one_sided_95_upper': silent_upper,
            'critical_discrepancy_count': len(critical_dois),
        }

    for doi, article in selected.items():
        output = appeer.get(doi, {})
        actual = {target: parse_day(output.get(target)) for target in TARGETS}
        truth = {}
        for target in TARGETS:
            row = truths.get((doi, target))
            if row and row['status'] == 'resolved' and row['confidence'] in {'A', 'B'}:
                truth[target] = parse_day(row['adjudicated_date'])
        if article['cohort'] == 'population_random' and eligible(article):
            if all(actual.values()):
                complete_triplets += 1
        if len(truth) == 3:
            triplet_truth += 1
            if all(actual.values()) and all(actual[key] == truth[key]
                                             for key in TARGETS):
                exact_triplets += 1
            if all(actual.values()):
                actual_review = (actual['accepted'] - actual['received']).days
                truth_review = (truth['accepted'] - truth['received']).days
                actual_post = (actual['published'] - actual['accepted']).days
                truth_post = (truth['published'] - truth['accepted']).days
                interval_errors['review_days'].append(actual_review - truth_review)
                interval_errors['post_acceptance_days'].append(actual_post - truth_post)
                interval_truth['review_days'].append(truth_review)
                interval_truth['post_acceptance_days'].append(truth_post)

    random_eligible = sum(
        article['cohort'] == 'population_random' and eligible(article)
        for article in selected.values())
    result['whole_record'] = {
        'complete_triplet_coverage': rate(complete_triplets, random_eligible),
        'exact_triplet_accuracy': rate(exact_triplets, triplet_truth),
    }
    for name, errors in interval_errors.items():
        result['intervals'][name] = {
            'truth_distribution': describe(interval_truth[name]),
            'signed_error': describe(errors),
            'absolute_error': describe([abs(value) for value in errors]),
        }

    dimensions = ('publisher', 'journal', 'year', 'article_type', 'oa_status')
    for dimension in dimensions:
        groups = defaultdict(lambda: [0, 0])
        for doi, article in selected.items():
            if article['cohort'] != 'population_random' or not eligible(article):
                continue
            key = article.get(dimension) or 'unknown'
            groups[key][1] += 1
            output = appeer.get(doi, {})
            if all(parse_day(output.get(target)) for target in TARGETS):
                groups[key][0] += 1
        result['missingness'][dimension] = {
            key: rate(values[0], values[1]) for key, values in groups.items()
        }
    result['selection_bias'] = selection_bias(selected, appeer, truths)

    target_coverage = [result['targets'][target]['coverage']['value']
                       for target in TARGETS]
    triplet_coverage = result['whole_record'][
        'complete_triplet_coverage']['value']
    journal_rates = [entry['value']
                     for entry in result['missingness']['journal'].values()
                     if entry['value'] is not None]
    if not target_coverage or any(value is None for value in target_coverage):
        operational = 'insufficient_evidence'
    elif (min(target_coverage) >= 0.90
          and triplet_coverage is not None and triplet_coverage >= 0.85
          and journal_rates and min(journal_rates) >= 0.75):
        operational = 'operationally_validated'
    else:
        operational = 'accurate_but_incomplete_or_failed'
    result['operational_verdict'] = {
        'verdict': operational,
        'minimum_field_coverage': min(target_coverage)
        if target_coverage and all(value is not None for value in target_coverage)
        else None,
        'complete_triplet_coverage': triplet_coverage,
        'minimum_journal_triplet_coverage': min(journal_rates)
        if journal_rates else None,
    }

    for target, publishers in per_target_publisher.items():
        result['publisher_verdicts'][target] = {}
        for publisher, counts in publishers.items():
            evidence = counts['reference_available']
            returned = counts['returned_evaluable']
            exact = counts['exact']
            exact_one = exact + counts['within_one_day']
            silent = counts['silent_wrong']
            exact_rate = rate(exact, returned)
            exact_one_rate = rate(exact_one, returned)
            silent_rate = rate(silent, returned)
            silent_upper = (wilson_interval(
                silent, returned, z=1.6448536269514722) or [None, None])[1]
            journal_evidence = per_target_publisher_journal[target][publisher]
            minimum_journal_evidence = min(journal_evidence.values(), default=0)
            if evidence < 80 or minimum_journal_evidence < 12:
                verdict = 'insufficient_evidence'
            elif (silent_rate['value'] is not None
                  and silent_rate['value'] <= 0.01
                  and silent_upper <= 0.03
                  and exact_rate['value'] >= 0.97
                  and exact_one_rate['value'] >= 0.99):
                verdict = 'date_accuracy_validated'
            else:
                verdict = 'failed_accuracy_threshold'
            result['publisher_verdicts'][target][publisher] = {
                'verdict': verdict,
                'reference_available': evidence,
                'minimum_journal_evidence': minimum_journal_evidence,
                'exact': exact_rate,
                'exact_or_one_day': exact_one_rate,
                'silent_wrong': silent_rate,
                'silent_wrong_one_sided_95_upper': silent_upper,
            }
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--sample', type=Path,
                        default=VALIDATION_ROOT / 'sampling' / 'sample.csv')
    result.add_argument(
        '--adjudications', type=Path,
        default=VALIDATION_ROOT / 'adjudication' / 'labels.csv')
    result.add_argument(
        '--appeer-results', type=Path,
        default=VALIDATION_ROOT / 'runs' / 'appeer-results.csv')
    result.add_argument('--split', choices=['development', 'holdout'],
                        default='holdout')
    result.add_argument(
        '--discrepancies', type=Path,
        default=VALIDATION_ROOT / 'adjudication' / 'discrepancies.csv')
    result.add_argument(
        '--output', type=Path,
        default=VALIDATION_ROOT / 'reports' / 'holdout-summary.json')
    return result


def main():
    args = parser().parse_args()
    summary = calculate(
        read_csv(args.sample), read_csv(args.adjudications),
        read_csv(args.appeer_results), args.split,
        read_csv(args.discrepancies))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
