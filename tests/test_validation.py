"""Offline tests for the reproducible validation-study tooling."""

import argparse
import csv
import json

from validation.scripts.analyze import calculate, wilson_interval
from validation.scripts import common
from validation.scripts.common import (
    StudyClient, canonical_doi, crossref_date, write_csv)
from validation.scripts.harvest import parse_jats_xml, parse_pubmed_xml
from validation.scripts.sample import SAMPLE_FIELDS, finalize


PROVENANCE = {
    'source_record_id': 'record-1',
    'source_url': 'https://example.test/record-1',
    'retrieved_at': '2026-08-20T00:00:00+00:00',
    'response_sha256': 'a' * 64,
    'raw_path': 'raw/example.xml',
}


def test_canonical_doi_is_strict():
    assert canonical_doi('https://doi.org/10.1000/ABC.1') == '10.1000/abc.1'
    assert canonical_doi('doi: 10.1000/example') == '10.1000/example'
    assert canonical_doi('https://example.org/10.1000/example') is None
    assert canonical_doi('10.1000/has whitespace') is None


def test_crossref_dates_preserve_precision():
    assert crossref_date({'date-parts': [[2025, 7, 11]]}) == (
        '2025-07-11', 'day')
    assert crossref_date({'date-parts': [[2025, 7]]}) == ('2025-07', 'month')
    assert crossref_date({'date-parts': [[2025]]}) == ('2025', 'year')
    assert crossref_date({'date-parts': [[2025, 2, 31]]}) == (None, 'unknown')


def test_study_client_honors_retry_after(monkeypatch):
    sleeps = []

    class Response:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f'unexpected HTTP {self.status_code}')

    class Session:
        def __init__(self):
            self.headers = {}
            self.responses = [Response(429, {'Retry-After': '2'}), Response(200)]

        def get(self, *args, **kwargs):
            return self.responses.pop(0)

    monkeypatch.setattr(common.time, 'sleep', sleeps.append)
    client = StudyClient(
        'appeer-validation-test/1.0 (mailto:test@example.org)',
        minimum_interval=0, session=Session())

    assert client.get('https://example.test').status_code == 200
    assert sleeps == [2.0]


def test_study_client_rejects_anonymous_placeholder():
    try:
        StudyClient('appeer-validation/0.1 (mailto:replace-with-study-contact)')
    except ValueError as error:
        assert 'transparent user agent' in str(error)
    else:  # pragma: no cover
        raise AssertionError('anonymous validation client was accepted')


def test_pubmed_history_is_extracted_by_explicit_status():
    content = b'''<PubmedArticleSet><PubmedArticle><PubmedData><History>
      <PubMedPubDate PubStatus="received"><Year>2024</Year><Month>5</Month><Day>6</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="accepted"><Year>2025</Year><Month>1</Month><Day>2</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="aheadofprint"><Year>2025</Year><Month>1</Month><Day>8</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="ppublish"><Year>2025</Year><Month>3</Month><Day>1</Day></PubMedPubDate>
    </History></PubmedData></PubmedArticle></PubmedArticleSet>'''

    rows = parse_pubmed_xml(content, '10.1000/example', PROVENANCE)
    observed = {(row['target_field'], row['semantic_concept']):
                row['normalized_date'] for row in rows
                if row['status'] == 'observed'}

    assert observed == {
        ('received', 'received'): '2024-05-06',
        ('accepted', 'accepted'): '2025-01-02',
        ('published', 'ahead_of_print'): '2025-01-08',
    }


def test_jats_history_keeps_online_and_accepted_manuscript_events():
    content = b'''<article><front><article-meta>
      <history>
        <date date-type="received" iso-8601-date="2024-05-06"/>
        <date date-type="accepted" iso-8601-date="2025-01-02"/>
        <event><date date-type="accepted-manuscript" iso-8601-date="2025-01-05"/></event>
      </history>
      <pub-date publication-format="electronic" date-type="pub" iso-8601-date="2025-01-08"/>
      <pub-date publication-format="electronic" date-type="collection" iso-8601-date="2025-02-01"/>
      <pub-date publication-format="print" date-type="pub" iso-8601-date="2025-03-01"/>
    </article-meta></front></article>'''

    rows = parse_jats_xml(content, '10.1000/example', PROVENANCE)
    published = [(row['semantic_concept'], row['normalized_date']) for row in rows
                 if row['target_field'] == 'published'
                 and row['status'] == 'observed']

    assert published == [
        ('accepted_manuscript', '2025-01-05'),
        ('published_online', '2025-01-08'),
    ]
    noncomparable = [row['semantic_concept'] for row in rows
                     if row['status'] == 'semantic_noncomparable']
    assert noncomparable == ['collection', 'print']


def test_enriched_selection_requires_explicit_lifecycle_evidence(tmp_path):
    study = {
        'years': [2025],
        'reference_enriched_per_cell': 3,
        'development_enriched_per_cell': 1,
    }
    journals = [{'publisher': 'ACS', 'journal': 'Example', 'issn': '0000-0000'}]
    study_path = tmp_path / 'study.json'
    journals_path = tmp_path / 'journals.json'
    study_path.write_text(json.dumps(study), encoding='utf-8')
    journals_path.write_text(json.dumps(journals), encoding='utf-8')

    candidates = []
    for index in range(7):
        candidates.append({
            'doi': f'10.1000/random-{index}', 'publisher': 'ACS',
            'journal': 'Example', 'issn': '0000-0000', 'year': '2025',
            'cohort': 'population_random',
            'split': 'development' if index < 3 else 'holdout',
            'selection_rank': f'{index:064d}',
        })
    for index in range(5):
        candidates.append({
            'doi': f'10.1000/enriched-{index}', 'publisher': 'ACS',
            'journal': 'Example', 'issn': '0000-0000', 'year': '2025',
            'cohort': 'reference_candidate', 'split': 'unassigned',
            'selection_rank': f'{index + 10:064d}',
        })
    candidate_path = tmp_path / 'candidates.csv'
    write_csv(candidate_path, SAMPLE_FIELDS, candidates)

    observation_path = tmp_path / 'observations.csv'
    fields = ['doi', 'target_field', 'status', 'explicit_or_inferred', 'precision']
    write_csv(observation_path, fields, [{
        'doi': f'10.1000/enriched-{index}', 'target_field': 'received',
        'status': 'observed', 'explicit_or_inferred': 'explicit',
        'precision': 'day',
    } for index in range(3)])

    output = tmp_path / 'sample.csv'
    finalize(argparse.Namespace(
        study=study_path, journals=journals_path, candidates=candidate_path,
        observations=observation_path, output=output))
    with output.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 10
    enriched = [row for row in rows if row['cohort'] == 'reference_enriched']
    assert [row['split'] for row in enriched] == [
        'development', 'holdout', 'holdout']


def sample_article(doi):
    return {
        'doi': doi, 'publisher': 'ACS', 'journal': 'Example',
        'issn': '0000-0000', 'year': '2025',
        'cohort': 'population_random', 'split': 'holdout',
        'eligibility': 'original_research', 'article_type': 'journal-article',
        'oa_status': 'unknown',
    }


def labels(doi, received, accepted, published):
    return [{
        'doi': doi, 'target_field': target, 'adjudicated_date': value,
        'status': 'resolved', 'confidence': 'A',
    } for target, value in zip(
        ('received', 'accepted', 'published'),
        (received, accepted, published))]


def test_analysis_separates_coverage_accuracy_and_omission():
    samples = [sample_article('10.1000/one'), sample_article('10.1000/two')]
    truths = (
        labels('10.1000/one', '2024-01-01', '2024-02-01', '2024-02-10')
        + labels('10.1000/two', '2024-03-01', '2024-04-01', '2024-04-10'))
    outputs = [
        {'doi': '10.1000/one', 'received': '2024-01-01',
         'accepted': '2024-02-01', 'published': '2024-02-10'},
        {'doi': '10.1000/two', 'received': '2024-03-02',
         'accepted': '2024-04-10', 'published': ''},
    ]

    result = calculate(samples, truths, outputs)

    assert result['targets']['received']['coverage']['value'] == 1
    assert result['targets']['received']['exact']['value'] == 0.5
    assert result['targets']['received']['exact_or_one_day']['value'] == 1
    assert result['targets']['accepted']['silent_wrong']['value'] == 0.5
    assert result['targets']['published']['coverage']['value'] == 0.5
    assert result['targets']['published']['omission']['value'] == 0.5
    assert result['whole_record']['complete_triplet_coverage']['value'] == 0.5
    assert result['whole_record']['exact_triplet_accuracy']['value'] == 0.5


def test_wilson_interval_handles_empty_denominator():
    assert wilson_interval(0, 0) is None
    lower, upper = wilson_interval(0, 100)
    assert lower == 0
    assert 0.03 < upper < 0.04
