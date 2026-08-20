"""Strict parser for current ACS Publications article pages."""

import functools

from appeer.parse.metadata import normalize_doi, normalize_whitespace
from appeer.parse.parsers.parser import Parser
from appeer.parse.parsers import soup_utils
from appeer.parse.parsers.structured import (
    citation_authors,
    first_meta,
    history_date,
    normalize_date,
)


class Parser_ACS_ANY_txt(Parser,
        publisher_code='ACS', journal_code='ANY', data_type='txt'):
    """Parse complete metadata from current ACS Publications HTML."""

    @staticmethod
    def check_publisher_journal(input_data, parser='html.parser'):
        soup, exception = soup_utils.convert_2_soup(input_data, parser=parser)
        if exception:
            return False, exception
        return (
            first_meta(soup, 'citation_publisher') == 'American Chemical Society'
            and bool(first_meta(soup, 'citation_title'))
            and bool(first_meta(soup, 'citation_journal_title')),
            None,
        )

    @functools.cached_property
    def doi(self):
        doi = normalize_doi(first_meta(self._input_data, 'citation_doi'))
        return doi if doi and doi.startswith('10.1021/') else None

    @functools.cached_property
    def publisher(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_publisher'))

    @functools.cached_property
    def journal(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_journal_title'))

    @functools.cached_property
    def title(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_title'))

    @functools.cached_property
    def publication_type(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_article_type'))

    @functools.cached_property
    def author_names(self):
        names, _ = citation_authors(self._input_data)
        return names

    @functools.cached_property
    def no_of_authors(self):
        return len(self.author_names) if self.author_names else None

    @functools.cached_property
    def affiliations(self):
        _, affiliations = citation_authors(self._input_data)
        return affiliations

    @functools.cached_property
    def received(self):
        return history_date(self._input_data, 'Received')

    @functools.cached_property
    def accepted(self):
        return history_date(self._input_data, 'Accepted')

    @functools.cached_property
    def published(self):
        return history_date(self._input_data, 'Published Online')

    @functools.cached_property
    def normalized_received(self):
        return normalize_date(self.received)

    @functools.cached_property
    def normalized_accepted(self):
        return normalize_date(self.accepted)

    @functools.cached_property
    def normalized_published(self):
        return normalize_date(self.published)
