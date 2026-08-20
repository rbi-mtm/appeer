"""Strict parser for the current RSC article layout."""

import functools

from appeer.parse.metadata import normalize_doi, normalize_whitespace
from appeer.parse.parsers.parser import Parser
from appeer.parse.parsers import soup_utils
from appeer.parse.parsers.structured import (
    citation_authors,
    first_meta,
    labelled_date_in_text,
    normalize_date,
    scholarly_jsonld,
    structured_authors,
)


class Parser_RSC_ANY_txt(Parser,
        publisher_code='RSC', journal_code='ANY', data_type='txt'):
    """Parse complete metadata from current Royal Society of Chemistry HTML."""

    @staticmethod
    def check_publisher_journal(input_data, parser='html.parser'):
        soup, exception = soup_utils.convert_2_soup(input_data, parser=parser)
        if exception:
            return False, exception
        publisher = first_meta(soup, 'citation_publisher', 'dc.publisher')
        return (
            publisher in ('Royal Society of Chemistry',
                          'The Royal Society of Chemistry')
            and bool(first_meta(soup, 'citation_title', 'dc.title'))
            and bool(first_meta(soup, 'citation_journal_title', 'dc.source')),
            None,
        )

    @functools.cached_property
    def doi(self):
        doi = normalize_doi(first_meta(
            self._input_data, 'citation_doi', 'dc.identifier'))
        return doi if doi and doi.startswith('10.1039/') else None

    @functools.cached_property
    def publisher(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_publisher', 'dc.publisher'))

    @functools.cached_property
    def journal(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_journal_title', 'dc.source'))

    @functools.cached_property
    def title(self):
        return normalize_whitespace(first_meta(
            self._input_data, 'citation_title', 'dc.title'))

    @functools.cached_property
    def publication_type(self):
        value = first_meta(self._input_data, 'citation_article_type', 'dc.type')
        if value:
            return normalize_whitespace(value)
        tag = self._input_data.find(attrs={'data-appeer': 'article-type'})
        return normalize_whitespace(tag.get_text()) if tag else None

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
        return labelled_date_in_text(self._input_data, 'Received')

    @functools.cached_property
    def accepted(self):
        return labelled_date_in_text(self._input_data, 'Accepted')

    @functools.cached_property
    def published(self):
        value = first_meta(self._input_data, 'citation_online_date',
                           'citation_publication_date', 'dc.date')
        return normalize_whitespace(value) or labelled_date_in_text(
            self._input_data, 'First published on')

    @functools.cached_property
    def normalized_received(self):
        return normalize_date(self.received)

    @functools.cached_property
    def normalized_accepted(self):
        return normalize_date(self.accepted)

    @functools.cached_property
    def normalized_published(self):
        return normalize_date(self.published)
