"""Opt-in checks against the official current publisher pages."""

import json
from pathlib import Path

import pytest

from appeer.parse.parsers.preparser import Preparser
from appeer.scrape.request import Request


FIXTURES = Path(__file__).parent / 'fixtures'


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
    assert request.success, request.error

    downloaded = tmp_path / fixture_name
    downloaded.write_text(request.response.text, encoding='utf-8')
    parser_class, _ = Preparser(str(downloaded)).determine_parser()
    assert parser_class is not None

    parser = parser_class(str(downloaded))
    assert parser.success, parser.invalid_fields
    assert parser.metadata == manifest['expected']
