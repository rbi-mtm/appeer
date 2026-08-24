"""Opt-in checks against the official current publisher pages."""

import json
from pathlib import Path

import pytest

from appeer.parse.parsers.preparser import Preparser
from appeer.scrape.request import Request


FIXTURES = Path(__file__).parent / 'fixtures'


INDEPENDENT_ARTICLES = [
    pytest.param(
        'https://pubs.acs.org/doi/10.1021/acsnano.5c00528',
        '10.1021/acsnano.5c00528',
        ('2025-01-09', '2025-02-26', '2025-03-05'),
        id='acs-nano',
    ),
    pytest.param(
        'https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.134.203602',
        '10.1103/physrevlett.134.203602',
        ('2024-10-12', '2025-04-14', '2025-05-20'),
        id='aps-physical-review-letters',
    ),
    pytest.param(
        'https://www.sciencedirect.com/science/article/pii/S0004370225000281',
        None,
        None,
        id='elsevier-artificial-intelligence',
    ),
]


def xfail_known_publisher_access_limit(request):
    if request.status == 403:
        pytest.xfail('publisher denied this transparent automated request')


@pytest.mark.slow
@pytest.mark.parametrize('fixture_name', [
    'nature_current_article.html',
    'rsc_current_article.html',
])
def test_official_current_article_matches_verified_metadata(fixture_name, tmp_path):
    manifest = json.loads(
        (FIXTURES / 'manifest.json').read_text(encoding='utf-8'))[fixture_name]
    request = Request(manifest['source_url'])
    request.send(max_tries=1, timeout=30)
    xfail_known_publisher_access_limit(request)
    assert request.success, request.error

    downloaded = tmp_path / fixture_name
    downloaded.write_text(request.response.text, encoding='utf-8')
    parser_class, _ = Preparser(str(downloaded)).determine_parser()
    assert parser_class is not None

    parser = parser_class(str(downloaded))
    assert parser.success, parser.invalid_fields
    assert parser.metadata == manifest['expected']


@pytest.mark.slow
@pytest.mark.parametrize(('url', 'expected_doi', 'expected_dates'),
                         INDEPENDENT_ARTICLES)
def test_additional_official_article_parses_live(
        url, expected_doi, expected_dates, tmp_path):
    request = Request(url)
    request.send(max_tries=1, timeout=30)
    xfail_known_publisher_access_limit(request)
    assert request.success, request.error

    downloaded = tmp_path / 'independent-article.html'
    downloaded.write_text(request.response.text, encoding='utf-8')
    parser_class, _ = Preparser(str(downloaded)).determine_parser()
    assert parser_class is not None

    parser = parser_class(str(downloaded))
    assert parser.success, parser.invalid_fields
    if expected_doi:
        assert parser.doi == expected_doi
    if expected_dates:
        assert (
            parser.normalized_received,
            parser.normalized_accepted,
            parser.normalized_published,
        ) == expected_dates
