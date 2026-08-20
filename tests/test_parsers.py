"""Offline scientific correctness tests for current publisher layouts."""

import hashlib
import json
from pathlib import Path

import pytest

from appeer.parse.parsers.preparser import Preparser
from appeer.parse.parsers.NAT.parser_NAT_ANY_txt import Parser_NAT_ANY_txt
from appeer.parse.parsers.RSC.parser_RSC_ANY_txt import Parser_RSC_ANY_txt


FIXTURES = Path(__file__).parent / 'fixtures'


def load_manifest():
    return json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('fixture_name', [
    'nature_block_page.html',
    'nature_current_article.html',
    'rsc_current_article.html',
    'unsupported_article.html',
])
def test_fixture_hashes_match_verified_manifest(fixture_name):
    fixture = FIXTURES / fixture_name
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert digest == load_manifest()[fixture_name]['sha256']


@pytest.mark.parametrize(('fixture_name', 'parser_class'), [
    ('rsc_current_article.html', Parser_RSC_ANY_txt),
    ('nature_current_article.html', Parser_NAT_ANY_txt),
])
def test_current_article_matrix(fixture_name, parser_class):
    manifest = load_manifest()[fixture_name]
    parser = parser_class(str(FIXTURES / fixture_name))

    assert parser.metadata == manifest['expected']
    assert parser.success
    assert parser.invalid_fields == []
    assert parser.warnings == []
    assert parser.provenance['raw_sha256'] == manifest['sha256']
    assert parser.provenance['parser'] == manifest['expected_parser']
    assert parser.provenance['package_version']
    assert parser.provenance['parsed_at']


@pytest.mark.parametrize('fixture_name', [
    'nature_block_page.html',
    'unsupported_article.html',
])
def test_non_articles_are_not_assigned_a_parser(fixture_name):
    parser_class, loaded = Preparser(str(FIXTURES / fixture_name)).determine_parser()
    assert parser_class is None
    assert loaded is None


def test_invalid_doi_is_a_hard_failure_but_partial_fields_remain(tmp_path):
    source = (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
    broken = tmp_path / 'invalid-doi.html'
    broken.write_text(source.replace(
        '10.1038/s41598-025-92476-w', '10.1038 malformed'), encoding='utf-8')

    parser = Parser_NAT_ANY_txt(str(broken))

    assert not parser.success
    assert parser.doi is None
    assert 'doi' in parser.invalid_fields
    assert parser.title.startswith('Chlorhexidine solutions')
    assert parser.author_names == ['Aiping Deng', 'Fangli Xiong', 'Qiuping Ren']


def test_impossible_date_is_a_hard_failure(tmp_path):
    source = (FIXTURES / 'rsc_current_article.html').read_text(encoding='utf-8')
    broken = tmp_path / 'invalid-date.html'
    broken.write_text(source.replace('3rd April 2025', '31st February 2025'),
                      encoding='utf-8')

    parser = Parser_RSC_ANY_txt(str(broken))

    assert not parser.success
    assert parser.received == '31st February 2025'
    assert parser.normalized_received is None
    assert 'normalized_received' in parser.invalid_fields


def test_chronology_anomaly_is_a_warning_not_a_parse_failure(tmp_path):
    source = (FIXTURES / 'rsc_current_article.html').read_text(encoding='utf-8')
    anomalous = tmp_path / 'chronology.html'
    anomalous.write_text(source.replace('25th June 2025', '2nd April 2025'),
                         encoding='utf-8')

    parser = Parser_RSC_ANY_txt(str(anomalous))

    assert parser.success
    assert parser.warnings == ['accepted_before_received']


def test_missing_affiliations_is_a_hard_failure(tmp_path):
    source = (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
    broken = tmp_path / 'missing-affiliations.html'
    broken.write_text(source.replace('"affiliation": [', '"missing": ['),
                      encoding='utf-8')

    parser = Parser_NAT_ANY_txt(str(broken))

    assert not parser.success
    assert parser.author_names
    assert parser.affiliations is None
    assert 'affiliations' in parser.invalid_fields
