"""Strict parser for current Elsevier ScienceDirect article pages."""

import functools

from appeer.parse.metadata import normalize_doi, normalize_whitespace
from appeer.parse.parsers.parser import Parser
from appeer.parse.parsers import soup_utils
from appeer.parse.parsers.structured import (
    assigned_json,
    citation_authors,
    first_meta,
    normalize_date,
    science_direct_authors,
)


class Parser_ELS_ANY_txt(Parser,
        publisher_code='ELS', journal_code='ANY', data_type='txt'):
    """Parse complete metadata from current ScienceDirect HTML."""

    @staticmethod
    def check_publisher_journal(input_data, parser='html.parser'):
        soup, exception = soup_utils.convert_2_soup(input_data, parser=parser)
        if exception:
            return False, exception
        return (
            first_meta(soup, 'citation_publisher') == 'Elsevier'
            and bool(first_meta(soup, 'citation_title'))
            and bool(first_meta(soup, 'citation_journal_title')),
            None,
        )

    @functools.cached_property
    def _state(self):
        return assigned_json(self._input_data, '__PRELOADED_STATE__')

    @functools.cached_property
    def _article(self):
        article = self._state.get('article', {})
        return article if isinstance(article, dict) else {}

    @functools.cached_property
    def _structured_authors(self):
        return science_direct_authors(self._state.get('authors'))

    @functools.cached_property
    def doi(self):
        doi = normalize_doi(self._article.get('doi') or first_meta(
            self._input_data, 'citation_doi', 'dc.identifier'))
        return doi if doi and doi.startswith('10.1016/') else None

    @functools.cached_property
    def publisher(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_publisher'))

    @functools.cached_property
    def journal(self):
        return normalize_whitespace(self._article.get('srctitle') or first_meta(
            self._input_data, 'citation_journal_title'))

    @functools.cached_property
    def title(self):
        return normalize_whitespace(self._article.get('titleString') or first_meta(
            self._input_data, 'citation_title'))

    @functools.cached_property
    def publication_type(self):
        return normalize_whitespace(
            self._article.get('documentTypeLabel') or first_meta(
                self._input_data, 'citation_article_type'))

    @functools.cached_property
    def author_names(self):
        names, _ = self._structured_authors
        if not names:
            names, _ = citation_authors(self._input_data)
        return names

    @functools.cached_property
    def no_of_authors(self):
        return len(self.author_names) if self.author_names else None

    @functools.cached_property
    def affiliations(self):
        _, affiliations = self._structured_authors
        if not affiliations:
            _, affiliations = citation_authors(self._input_data)
        return affiliations

    @functools.cached_property
    def _dates(self):
        dates = self._article.get('dates', {})
        return dates if isinstance(dates, dict) else {}

    @functools.cached_property
    def received(self):
        return normalize_whitespace(self._dates.get('Received'))

    @functools.cached_property
    def accepted(self):
        return normalize_whitespace(self._dates.get('Accepted'))

    @functools.cached_property
    def published(self):
        return normalize_whitespace(
            self._dates.get('Available online')
            or first_meta(self._input_data, 'citation_online_date')
            or self._dates.get('Version of Record'))

    @functools.cached_property
    def normalized_received(self):
        return normalize_date(self.received)

    @functools.cached_property
    def normalized_accepted(self):
        return normalize_date(self.accepted)

    @functools.cached_property
    def normalized_published(self):
        return normalize_date(self.published)
