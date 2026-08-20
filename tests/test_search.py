"""Inclusive search filters, JSON export, and safe aggregate tests."""

import json
import math
from pathlib import Path

import pytest

from appeer.db.pub_db import PubDB
from appeer.parse.parsers import date_utils
from appeer.pub.researcher import PubReSearcher


FIXTURES = Path(__file__).parent / 'fixtures'


def fixture_metadata(name):
    manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    return manifest[name]['expected'].copy()


@pytest.fixture
def publication_database(tmp_path):
    path = tmp_path / 'pub.db'
    database = PubDB(db_path=path)
    database.create_database()
    database.pub.add_entry(**fixture_metadata('nature_current_article.html'))
    database.pub.add_entry(**fixture_metadata('rsc_current_article.html'))
    database.close()
    return path


def test_partial_date_normalization_uses_period_boundaries():
    assert date_utils.normalize_date_2iso('2025') == '2025-01-01'
    assert date_utils.normalize_date_2iso('2025', end=True) == '2025-12-31'
    assert date_utils.normalize_date_2iso('2024-02', end=True) == '2024-02-29'
    assert date_utils.normalize_date_2iso('2025-02', end=True) == '2025-02-28'


def test_maximum_year_and_month_are_inclusive(publication_database):
    with PubReSearcher(db_path=publication_database) as researcher:
        researcher.search_pub(max_received='2025')
        assert {entry.doi for entry in researcher.filtered_pubs} == {
            '10.1038/s41598-025-92476-w', '10.1039/d5nj01475a'}

        researcher.search_pub(max_received='2025-03')
        assert [entry.doi for entry in researcher.filtered_pubs] == [
            '10.1038/s41598-025-92476-w']

        researcher.search_pub(min_received='2025')
        assert [entry.doi for entry in researcher.filtered_pubs] == [
            '10.1039/d5nj01475a']


def test_inverted_ranges_are_rejected(publication_database):
    with PubReSearcher(db_path=publication_database) as researcher:
        with pytest.raises(ValueError, match='invalid filter'):
            researcher.search_pub(
                min_received='2025-05', max_received='2025-04')


def test_json_output_and_author_names(publication_database, tmp_path):
    output = tmp_path / 'search.json'
    with PubReSearcher(db_path=publication_database) as researcher:
        researcher.search_pub(
            normalized_publisher='Nature Portfolio',
            get_title=True,
            get_author_names=True,
            get_affiliations=True,
        )
        researcher.write_json(output)

    payload = json.loads(output.read_text(encoding='utf-8'))
    assert len(payload) == 1
    assert payload[0]['author_names'] == ['Aiping Deng', 'Fangli Xiong', 'Qiuping Ren']
    assert len(payload[0]['affiliations'][2]) == 4
    assert payload[0]['title'].startswith('Chlorhexidine solutions')


def test_suspicious_intervals_are_excluded_from_aggregates(tmp_path):
    path = tmp_path / 'pub.db'
    metadata = fixture_metadata('rsc_current_article.html')
    metadata['normalized_accepted'] = '2025-04-02'
    metadata['accepted'] = '2nd April 2025'

    database = PubDB(db_path=path)
    database.create_database()
    database.pub.add_entry(**metadata)
    database.close()

    with PubReSearcher(db_path=path) as researcher:
        researcher.search_pub()
        entry = researcher.filtered_pubs[0]
        assert entry.received_2_accepted is None
        assert math.isnan(
            researcher.analyzer.basic_search_results['average_ra'])
