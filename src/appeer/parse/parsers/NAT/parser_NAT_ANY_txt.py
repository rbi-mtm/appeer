"""Strict parser for the current Nature Portfolio article layout."""

import functools

from appeer.parse.metadata import normalize_doi, normalize_whitespace
from appeer.parse.parsers.parser import Parser
from appeer.parse.parsers import soup_utils
from appeer.parse.parsers.structured import (
    citation_authors,
    first_meta,
    history_date,
    normalize_date,
    scholarly_jsonld,
    structured_authors,
)


class Parser_NAT_ANY_txt(Parser,
        publisher_code='NAT', journal_code='ANY', data_type='txt'):
    """Parse complete metadata from current Nature Portfolio HTML."""

    @staticmethod
    def check_publisher_journal(input_data, parser='lxml'):
        soup, exception = soup_utils.convert_2_soup(input_data, parser=parser)
        if exception:
            return False, exception
        publisher = first_meta(soup, 'citation_publisher', 'dc.publisher')
        doi = normalize_doi(first_meta(soup, 'citation_doi', 'dc.identifier'))
        return (
            publisher in ('Nature Publishing Group', 'Nature Research',
                          'Nature Portfolio', 'Springer Nature')
            and bool(doi and doi.startswith('10.1038/')),
            None,
        )

    @functools.cached_property
    def doi(self):
        return normalize_doi(first_meta(
            self._input_data, 'citation_doi', 'dc.identifier', 'doi'))

    @functools.cached_property
    def publisher(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_publisher', 'dc.publisher'))

    @functools.cached_property
    def journal(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_journal_title'))

    @functools.cached_property
    def title(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_title', 'dc.title'))

    @functools.cached_property
    def publication_type(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_article_type', 'dc.type'))

    @functools.cached_property
    def author_names(self):
        names, _ = structured_authors(self._input_data)
        if not names:
            names, _ = citation_authors(self._input_data)
        return names

    @functools.cached_property
    def no_of_authors(self):
        return len(self.author_names) if self.author_names else None

    @functools.cached_property
    def affiliations(self):
        _, affiliations = structured_authors(self._input_data)
        if not affiliations:
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
        return (history_date(self._input_data, 'Published')
                or first_meta(self._input_data, 'citation_online_date', 'dc.date')
                or scholarly_jsonld(self._input_data).get('datePublished'))

    @functools.cached_property
    def normalized_received(self):
        return normalize_date(self.received)

    @functools.cached_property
    def normalized_accepted(self):
        return normalize_date(self.accepted)

    @functools.cached_property
    def normalized_published(self):
        value = self.published[:10] if self.published else None
        return normalize_date(value)
