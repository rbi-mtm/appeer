"""Offline tests for the reproducible validation-study tooling."""

import csv
import json
from pathlib import Path

from validation.scripts.analyze import calculate, wilson_interval
from validation.scripts import common
from validation.scripts.common import (
    StudyClient, canonical_doi, crossref_date, write_csv)
from validation.scripts.harvest import parse_jats_xml, parse_pubmed_xml
from validation.scripts.pre_adjudication import compare, reference_summary
from validation.scripts.run_appeer import parse_file, retrieve
from validation.scripts.sample import fetch_frame, select
from validation.scripts.screen_eligibility import classify


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


def test_crossref_frame_allows_reused_advancing_cursor(tmp_path, monkeypatch):
    pages = [
        {'items': [{'DOI': '10.1000/one', 'title': ['One'],
                    'type': 'journal-article'}], 'next-cursor': 'same'},
        {'items': [{'DOI': '10.1000/two', 'title': ['Two'],
                    'type': 'journal-article'}], 'next-cursor': 'same'},
        {'items': [], 'next-cursor': 'same'},
    ]

    class Response:
        def __init__(self, message):
            self.message = message

        def json(self):
            return {'message': self.message}

    class Client:
        def get(self, *args, **kwargs):
            return Response(pages.pop(0))

    path = tmp_path / 'frame.jsonl'
    monkeypatch.setattr(
        'validation.scripts.sample.frame_path', lambda journal, year: path)
    monkeypatch.setattr('validation.scripts.sample.VALIDATION_ROOT', tmp_path)
    result = fetch_frame(Client(), {
        'publisher': 'ACS', 'journal': 'Example', 'issn': '0000-0000',
    }, 2025, refresh=True)

    assert result['record_count'] == 2
    assert len(path.read_text(encoding='utf-8').splitlines()) == 2


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


def test_title_screen_excludes_only_explicit_nonresearch_labels():
    assert classify('Author Correction: Example')[:2] == (
        'ineligible', 'correction')
    assert classify('A systematic review of examples')[0] == (
        'systematic_review')
    assert classify('Error correction in quantum systems')[0] == 'uncertain'


def test_reference_summary_does_not_turn_missingness_into_error():
    missing = reference_summary([{
        'target_field': 'accepted', 'status': 'source_field_missing',
        'explicit_or_inferred': '', 'normalized_date': '',
        'semantic_concept': '', 'source': 'crossref',
        'source_lineage': 'publisher_deposit',
    }], 'accepted')
    assert missing['status'] == 'reference_unavailable'
    assert missing['date'] == ''

    agreement = reference_summary([{
        'target_field': 'accepted', 'status': 'observed',
        'explicit_or_inferred': 'explicit', 'normalized_date': '2025-01-02',
        'semantic_concept': 'accepted', 'source': source,
        'source_lineage': lineage,
    } for source, lineage in (
        ('pubmed', 'pubmed_deposit'), ('pmc_jats', 'pmc_deposit'))], 'accepted')
    assert agreement['status'] == 'multi_source_agreement'
    assert agreement['date'] == '2025-01-02'

    assert compare(agreement, '', True, 'failed', 'false') == (
        'appeer_transport_unavailable', '')
    assert compare(agreement, '', True, 'retrieved', 'false') == (
        'appeer_parse_failed_reference_exists', '')


def test_validation_runner_records_frozen_parser_output():
    result = parse_file(
        Path('tests/fixtures/acs_jacs_current_article.html'),
        '10.1021/jacs.5c11789', 'frozen-revision')

    assert result['success'] == 'true'
    assert result['parser'] == 'Parser_ACS_ANY_txt'
    assert result['published'] == '2025-11-10'
    assert result['git_revision'] == 'frozen-revision'
    assert len(result['input_sha256']) == 64


def test_elsevier_runner_follows_safe_linking_hub_pii():
    class Response:
        def __init__(self, status, location=''):
            self.status_code = status
            self.headers = {'Location': location} if location else {}

    class Session:
        def __init__(self):
            self.urls = []
            self.responses = [
                Response(302, 'https://linkinghub.elsevier.com/retrieve/pii/S123'),
                Response(200),
                Response(200),
            ]

        def get(self, url, **kwargs):
            self.urls.append(url)
            return self.responses.pop(0)

    session = Session()
    response, final_url = retrieve(
        session, '10.1016/j.example.2025.1', 'ELS', 30, 'test-agent', 0)

    assert response.status_code == 200
    assert final_url == 'https://www.sciencedirect.com/science/article/pii/S123'
    assert session.urls[-1] == final_url


def test_confirmatory_selection_uses_only_population_frame(tmp_path, monkeypatch):
    study = {
        'protocol_version': 2,
        'seed': 'test-seed',
        'years': [2025],
        'population_random_per_cell': 10,
        'development_random_per_cell': 4,
    }
    journals = [{'publisher': 'ACS', 'journal': 'Example', 'issn': '0000-0000'}]
    study_path = tmp_path / 'study.json'
    journals_path = tmp_path / 'journals.json'
    study_path.write_text(json.dumps(study), encoding='utf-8')
    journals_path.write_text(json.dumps(journals), encoding='utf-8')

    frame = tmp_path / 'ACS-0000-0000-2025.jsonl'
    with frame.open('w', encoding='utf-8') as stream:
        for index in range(12):
            stream.write(json.dumps({
                'doi': f'10.1000/random-{index}', 'publisher': 'ACS',
                'journal': 'Example', 'issn': '0000-0000', 'year': '2025',
                'article_type': 'journal-article',
                'title': f'Article {index}',
                'crossref_url': f'https://doi.org/10.1000/random-{index}',
            }) + '\n')

    monkeypatch.setattr(
        'validation.scripts.sample.frame_path', lambda journal, year: frame)
    (tmp_path / 'sampling').mkdir()
    (tmp_path / 'sampling' / 'frame-manifest.csv').write_text(
        'frame\n', encoding='utf-8')
    monkeypatch.setattr('validation.scripts.sample.VALIDATION_ROOT', tmp_path)

    output = tmp_path / 'sample.csv'
    class Args:
        pass

    args = Args()
    args.study = study_path
    args.journals = journals_path
    args.output = output
    select(args)
    with output.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 10
    assert {row['cohort'] for row in rows} == {'population_random'}
    assert [row['split'] for row in rows].count('development') == 4
    assert [row['split'] for row in rows].count('holdout') == 6
    manifest = json.loads((tmp_path / 'sample-manifest.json').read_text())
    assert manifest['article_count'] == 10


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
