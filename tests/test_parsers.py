"""Offline scientific correctness tests for current publisher layouts."""

import hashlib
import json
from pathlib import Path

import pytest

from appeer.parse.parsers.preparser import Preparser
from appeer.parse.parsers import parser as parser_module
from appeer.parse.parsers.ACS.parser_ACS_ANY_txt import Parser_ACS_ANY_txt
from appeer.parse.parsers.APS.parser_APS_ANY_txt import Parser_APS_ANY_txt
from appeer.parse.parsers.ELS.parser_ELS_ANY_txt import Parser_ELS_ANY_txt
from appeer.parse.parsers.NAT.parser_NAT_ANY_txt import Parser_NAT_ANY_txt
from appeer.parse.parsers.RSC.parser_RSC_ANY_txt import Parser_RSC_ANY_txt


FIXTURES = Path(__file__).parent / 'fixtures'


def load_manifest():
    return json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('fixture_name', [
    'acs_catalysis_current_article.html',
    'acs_jacs_current_article.html',
    'aps_pra_current_article.html',
    'aps_prb_current_article.html',
    'elsevier_cleaner_current_article.html',
    'elsevier_trac_current_article.html',
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
    ('acs_catalysis_current_article.html', Parser_ACS_ANY_txt),
    ('acs_jacs_current_article.html', Parser_ACS_ANY_txt),
    ('aps_pra_current_article.html', Parser_APS_ANY_txt),
    ('aps_prb_current_article.html', Parser_APS_ANY_txt),
    ('elsevier_cleaner_current_article.html', Parser_ELS_ANY_txt),
    ('elsevier_trac_current_article.html', Parser_ELS_ANY_txt),
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


@pytest.mark.parametrize(('fixture_name', 'parser_class'), [
    ('acs_jacs_current_article.html', Parser_ACS_ANY_txt),
    ('aps_pra_current_article.html', Parser_APS_ANY_txt),
    ('elsevier_trac_current_article.html', Parser_ELS_ANY_txt),
])
def test_preparser_routes_new_publishers(fixture_name, parser_class):
    selected, loaded = Preparser(str(FIXTURES / fixture_name)).determine_parser()

    assert selected is parser_class
    assert loaded is not None


def test_acs_published_online_is_published_not_issue_date():
    parser = Parser_ACS_ANY_txt(
        str(FIXTURES / 'acs_jacs_current_article.html'))

    assert parser.published == 'November 10, 2025'
    assert parser.normalized_published == '2025-11-10'
    assert 'November 26, 2025' in parser._input_data.get_text(' ', strip=True)


def test_sciencedirect_requires_version_of_record_date(tmp_path):
    source = (FIXTURES / 'elsevier_trac_current_article.html').read_text(
        encoding='utf-8')
    without_version_of_record = tmp_path / 'available-online-only.html'
    without_version_of_record.write_text(
        source.replace('"Version of Record":"10 February 2025"',
                       '"Unrelated date":"10 February 2025"'),
        encoding='utf-8',
    )

    parser = Parser_ELS_ANY_txt(str(without_version_of_record))

    assert parser.received == '17 November 2024'
    assert parser.accepted == '26 January 2025'
    assert parser.published is None
    assert not parser.success
    assert 'published' in parser.invalid_fields
    assert 'normalized_published' in parser.invalid_fields


def test_invalid_doi_is_a_hard_failure_but_partial_fields_remain(tmp_path):
    source = (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
    broken = tmp_path / 'invalid-doi.html'
    broken.write_text(source.replace(
        '10.1038/s41598-025-92476-w', '10.1038 malformed'), encoding='utf-8')

    parser = Parser_NAT_ANY_txt(str(broken))
    selected, _ = Preparser(str(broken)).determine_parser()

    assert not parser.success
    assert selected is Parser_NAT_ANY_txt
    assert parser.doi is None
    assert 'doi' in parser.invalid_fields
    assert parser.title.startswith('Chlorhexidine solutions')
    assert parser.author_names == ['Aiping Deng', 'Fangli Xiong', 'Qiuping Ren']


def test_publisher_mismatched_doi_prefix_is_a_hard_failure(tmp_path):
    source = (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
    broken = tmp_path / 'wrong-prefix.html'
    broken.write_text(source.replace(
        '10.1038/s41598-025-92476-w', '10.1039/d5nj01475a'), encoding='utf-8')

    parser = Parser_NAT_ANY_txt(str(broken))

    assert not parser.success
    assert parser.doi is None
    assert 'doi' in parser.invalid_fields


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


def test_git_provenance_is_resolved_from_the_package_repository(monkeypatch):
    observed = {}

    class Result:
        stdout = 'abc123\n'

    def fake_run(command, **kwargs):
        observed['command'] = command
        observed['kwargs'] = kwargs
        return Result()

    monkeypatch.setattr(parser_module.subprocess, 'run', fake_run)

    assert Parser_NAT_ANY_txt._git_revision() == 'abc123'
    assert observed['command'][:2] == ['git', '-C']
    assert Path(observed['command'][2]) == Path(__file__).parents[1]
    assert observed['command'][3:] == ['rev-parse', '--verify', 'HEAD']
