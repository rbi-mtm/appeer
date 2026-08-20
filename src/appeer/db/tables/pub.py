"""Handles the ``pub`` table in ``pub.db``"""

import json
import sqlite3
import datetime
import re
from collections import namedtuple

import click

from appeer.db.tables.table import Table
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.parse.default_metadata import default_metadata
from appeer.parse.metadata import (
    PROVENANCE_FIELDS,
    normalize_doi,
    validate_metadata,
)
from appeer.parse.parsers import date_utils

import appeer.general.utils as _utils

JournalSummary = namedtuple('JournalSummary',
        ['name',
        'count',
        'publication_types',
        'min_received',
        'max_received',
        'min_accepted',
        'max_accepted',
        'min_published',
        'max_published']
        )

FilteredPub = namedtuple(typename='FilteredPub',
        field_names=['doi',
        'publisher',
        'journal',
        'normalized_received',
        'normalized_accepted',
        'normalized_published',
        'received_2_accepted',
        'received_2_published',
        'accepted_2_published',
        'title',
        'publication_type',
        'no_of_authors',
        'author_names',
        'affiliations',
        'warnings'],
        defaults=[None, None, None, None, None, None]
        )

class Pub(Table,
           name='pub',
           columns=get_registered_tables()['pub']):
    """
    Handles the ``pub`` table

    Parameters
    ----------
    name : str
        Table name
    columns : str
        List of column names

    """

    def __init__(self, connection):
        """
        Establishes a connection with the the jobs database

        connection : sqlite3.Connection
            Connection to the database to which the table belongs to

        """

        super().__init__(connection=connection)

    def initialize_table(self, commit=True):
        """
        Initializes an empty table

        This method overrides the ``initialize_table()`` method
            of the parent Table class. The reason is that we
            want to explicitly define ``doi`` as the primary table
            key.

        Possibly, in the future, all tables could be redefined
            with an explicit primary key.

        """

        self._sanity_check()

        super().initialize_table(commit=commit)

    def add_entry(self, overwrite=False, **kwargs):
        """
        Adds or replaces an entry in the ``pub`` table

        Each entry in the ``pub`` table must have a unique ``doi`` value.

            If an entry containing a DOI value already existing in the table
                is attempted to be added to the database, the ``overwrite``
                parameter governs the behavior of this method:

                (1) If ``overwrite == False``, the entry is not inserted

                (2) If ``overwrite == True``, the entry with the given
                    DOI is updated

        Parameters
        ----------
        overwrite : bool
            If False, ignore a duplicate DOI entry (default);
                if True, overwrite a duplicate DOI entry;
                if the given DOI is unique, this parameter has no impact

        Keyword Arguments
        -----------------
        doi : str
            DOI of the publication
        publisher : str
            Publisher
        journal : str
            Publication journal
        title : str
            Title of the publication
        publication_type : str
            Type of publication
        no_of_authors : int
            Number of publication authors
        affiliations : str
            Author affiliations
        received : str
            Date of the publication reception
        accepted : str
            Date of the publication acceptance
        published : str
            Date of publication
        normalized_received : str
            Date of the publication reception in YYYY-MM-DD format
        normalized_accepted : str
            Date of the publication acceptance in YYYY-MM-DD format
        normalized_published : str
            Date of publication in YYYY-MM-DD format
        normalized_publisher : str
            Publisher in the standard format;
                as defined in parse/parsers/publishers_index.json
        normalized_publisher : str
            Journal in the standard format;
                as defined in parse/parsers/PUBLISHER/PUBLISHER_journals.json

        Returns
        -------
        duplicate : bool
            Whether the entry DOI is a duplicate
        inserted : bool
            Whether the entry was inserted into the table

        """

        duplicate = False
        inserted = False

        columns = default_metadata() + list(PROVENANCE_FIELDS)
        data = {column: kwargs.get(column) for column in columns}
        for column in ('author_names', 'affiliations'):
            value = data[column]
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f'{column} must contain a JSON list.') from exc
            if column == 'author_names' and value and isinstance(value[0], list):
                if not all(len(entry) == 1 for entry in value):
                    raise ValueError(
                        'Each serialized author entry must contain one name.')
                value = [entry[0] for entry in value]
            data[column] = value

        invalid_fields, detected_warnings = validate_metadata(data)
        if invalid_fields:
            raise ValueError(
                'Publication metadata is incomplete or invalid: '
                + ', '.join(invalid_fields))
        data['doi'] = normalize_doi(data['doi'])

        warnings = data.get('warnings')
        if isinstance(warnings, str):
            try:
                warnings = json.loads(warnings)
            except json.JSONDecodeError as exc:
                raise ValueError('warnings must contain a JSON list.') from exc
        if not isinstance(warnings, list) or not all(
                isinstance(warning, str) for warning in warnings):
            raise ValueError('warnings must be a list of strings.')
        warnings = list(dict.fromkeys(warnings + detected_warnings))

        if not isinstance(data['raw_sha256'], str) or not re.fullmatch(
                r'[0-9a-fA-F]{64}', data['raw_sha256']):
            raise ValueError('raw_sha256 must be a 64-character hexadecimal hash.')
        for field in ('parser', 'package_version'):
            if not isinstance(data[field], str) or not data[field].strip():
                raise ValueError(f'{field} must be a nonempty string.')
        try:
            datetime.datetime.fromisoformat(data['parsed_at'])
        except (TypeError, ValueError) as exc:
            raise ValueError('parsed_at must be an ISO datetime.') from exc
        if data['git_revision'] is not None and not isinstance(
                data['git_revision'], str):
            raise ValueError('git_revision must be a string or null.')

        data['author_names'] = json.dumps(
            data['author_names'], ensure_ascii=False)
        data['affiliations'] = json.dumps(
            data['affiliations'], ensure_ascii=False)
        data['warnings'] = json.dumps(warnings, ensure_ascii=False)

        columns_sql = ', '.join(columns)
        colons_values = ', '.join(':' + column for column in columns)
        add_query = (f'INSERT INTO {self._name} ({columns_sql}) '
                     f'VALUES({colons_values})')

        try:

            self._cur.execute(add_query, data)
            self._con.commit()

            inserted = True

        except sqlite3.IntegrityError:

            self._con.rollback()

            duplicate = True

            if overwrite:

                replace_query = (f'REPLACE INTO {self._name} ({columns_sql}) '
                                 f'VALUES({colons_values})')

                self._cur.execute(replace_query, data)
                self._con.commit()

                inserted = True

            else:
                pass

        except BaseException:
            self._con.rollback()
            raise

        return duplicate, inserted

    def update_entry(self, **kwargs):
        """
        Entries in the ``pub`` table should not be directly updated

        Instead, a commit job with ``overwrite=True`` should be run.

        """

        raise PermissionError('Directly updating entries in the "pub" table of the "pub.db" database is not permitted; to update an entry, run a commit job with overwrite=True instead.')

    def delete_entry(self, **kwargs):
        """
        Deletes an entry given by the ``doi`` keyword argument

        Keyword Arguments
        -----------------
        doi : str
            DOI of the publication

        Returns
        -------
        success : bool
            True if the entry was removed, False if it was not

        """

        doi = kwargs['doi']

        click.echo(f'Removing entry {doi} from the {self._name} table ...')

        exists = self.pub_exists(doi)

        if not exists:

            click.echo(f'Entry {doi} does not exist in the {self._name} table.')
            success = False

        else:

            self._sanity_check()

            delete_query = f'DELETE FROM {self._name} where doi = ?'

            self._cur.execute(delete_query, (doi,))

            self._con.commit()

            exists = self.pub_exists(doi)

            if not exists:

                click.echo(f'Entry {doi} removed.\n')
                success = True

            else:
                click.echo(f'Could not delete entry {doi}\n')
                success = False

        return success

    def pub_exists(self, doi):
        """
        Checks whether the entry with the given DOI exists in the table

        Parameters
        ----------
        doi : str
            DOI of the publication

        Returns
        -------
        exists : bool
            True if entry exists, False if it does not

        """

        exists = bool(self.get_pub(doi=doi))

        return exists

    def get_pub(self, doi):
        """
        Returns a named tuple corresponding to the entry with the given DOI

        Parameters
        ----------
        doi : str
            DOI of the publication

        Returns
        -------
        pub : appeer.db.tables.pub._pub
            The sought publication entry

        """

        pub = self._search_table(doi=doi)

        if pub:
            pub = pub[0]
            pub = pub._replace(
                author_names=json.loads(pub.author_names),
                affiliations=json.loads(pub.affiliations),
                warnings=json.loads(pub.warnings or '[]'),
            )

        return pub

    def get_unique_publishers(self):
        """
        Get a list of publishers found in the table

        Returns
        -------
        unique_publishers : list of str
            List of unique publishers in the pub table

        """

        self._sanity_check()

        query = f"""SELECT DISTINCT normalized_publisher FROM {self._name}
                ORDER BY normalized_publisher"""

        self._cur.execute(query)
        search_results = self._cur.fetchall()

        unique_publishers = [result[0] for result in search_results]

        return unique_publishers

    def get_unique_journals(self, publisher):
        """
        Get a list of journals for a given publisher

        Returns
        -------
        unique_journals : list of str | None
            List of unique journals for a given publisher;
                None if publisher doesn't exist

        """

        self._sanity_check()

        unique_publishers = self.get_unique_publishers()

        if publisher not in unique_publishers:
            return None

        query = f"""SELECT DISTINCT normalized_journal FROM {self._name}
                WHERE normalized_publisher = ?
                ORDER BY normalized_journal"""

        self._cur.execute(query, (publisher,))
        search_results = self._cur.fetchall()

        unique_journals = [result[0] for result in search_results]

        return unique_journals

    def get_publisher_summary(self, publisher):
        """
        Get a summary of journals found for a given ``publisher``

        - Finds distinct normalized journal names

        - Counts how many entries are found for each journal

        - Finds distinct publication types

            NOTE: Publication types are currently in experimental/unstable
            stage as they are not normalized.

        - Finds the earliest/latest normalized received date for each journal

        - Finds the earliest/latest normalized accepted date for each journal

        - Finds the earliest/latest normalized published date for each journal

        The results are returned in a list of JournalSummary named tuples

        Parameters
        ----------
        publisher : str
            A normalized publisher name

        Returns
        -------
        publisher_summary : list of appeer.db.tables.pub.JournalSummary | None
            Summary of unique journals for a given publisher;
                None if publisher does not exist in the table

        """

        self._sanity_check()

        unique_publishers = self.get_unique_publishers()

        if publisher not in unique_publishers:
            return None

        query = f"""

                SELECT normalized_journal,

                COUNT(normalized_journal),

                GROUP_CONCAT(DISTINCT publication_type||'|'),

                MIN(normalized_received),
                MAX(normalized_received),

                MIN(normalized_accepted),
                MAX(normalized_accepted),

                MIN(normalized_published),
                MAX(normalized_published)

                FROM {self._name}
                WHERE normalized_publisher = ?

                GROUP BY normalized_journal
                ORDER BY normalized_journal

                """

        self._cur.execute(query, (publisher,))

        publisher_summary = list(
                map(JournalSummary._make, self._cur.fetchall())
                )

        return publisher_summary

    def get_journal_summary(self, publisher, journal):
        """
        Get a summary of a ``journal`` of a given ``publisher``

        - Counts how many entries are found for the journal

        - Finds distinct publication types

            NOTE: Publication types are currently in experimental/unstable
            stage as they are not normalized.

        - Finds the earliest/latest normalized received date for the journal

        - Finds the earliest/latest normalized accepted date for the journal

        - Finds the earliest/latest normalized published date for the journal

        The result is returned as a JournalSummary named tuple

        Parameters
        ----------
        publisher : str
            Normalized publisher name
        journal : str
            Normalized journal name

        Returns
        -------
        journal_summary : appeer.db.tables.pub.JournalSummary | None
            Summary of a journal for a given publisher;
                None if publisher or journal do not exist in the table

        """

        self._sanity_check()

        unique_publishers = self.get_unique_publishers()

        if publisher not in unique_publishers:
            return None

        unique_journals = self.get_unique_journals(publisher=publisher)

        if journal not in unique_journals:
            return None

        query = f"""

                SELECT normalized_journal,

                COUNT(normalized_journal),

                GROUP_CONCAT(DISTINCT publication_type||'|'),

                MIN(normalized_received),
                MAX(normalized_received),

                MIN(normalized_accepted),
                MAX(normalized_accepted),

                MIN(normalized_published),
                MAX(normalized_published)

                FROM {self._name}

                WHERE normalized_publisher = ?
                AND normalized_journal = ?

                """

        self._cur.execute(query, (publisher, journal))

        journal_summary = list(
                map(JournalSummary._make, self._cur.fetchall())
                )[0]

        return journal_summary

    def filter_pjt(self,
                   get_title=False,
                   get_publication_type=False,
                   get_no_of_authors=False,
                   get_author_names=False,
                   get_affiliations=False,
                   **kwargs):
        """
        Filter the ``pub`` table and retrieve the results

        The acceptable formats for received/accepted/published dates are:

            (1) YYYY
            (2) YYYY-MM
            (3) YYYY-MM-DD

        The results are ordered by the following in ascending order:

            (1) Publisher
            (2) Journal
            (3) Received date
            (4) Accepted date

        Parameters
        ----------
        get_title : bool
            Include titles of the filtered entries to the result;
                False by default
        get_publication_type : bool
            Include publication types of the filtered entries;
                False by default
        get_no_of_authors : bool
            Include number of authors of the filtered entries to the result;
                False by default
        get_author_names : bool
            Include author names of the filtered entries to the result;
                False by default
        get_affiliations : bool
            Include affiliations of the filtered entries to the result;
                False by default

        Keyword Arguments
        -----------------
        normalized_publisher : list of str
            Normalized publisher name(s)
        normalized_journal : list of str
            Normalized journal name(s)
        min_received : str
            Earliest date of publication reception
        max_received : str
            Latest date of publication reception
        min_accepted : str
            Earliest date of publication acceptance
        max_accepted : str
            Latest date of publication acceptance
        min_published : str
            Earliest date of publication
        max_published : str
            Latest date of publication
        publication_types : str
            List of str; note that publication types are experimental

        Returns
        -------
        filtered_entries : list of appeer.db.tables.pub.FilteredPub
            Entries satisfying the inputted filters;
                empty list if no entries satisfying the filters are found

        Raises
        ------
        ValueError
            In the case of invalid filters

        """

        self._sanity_check()

        try:
            add_2_query, args_query = self._prepare_filters(**kwargs)

        except ValueError as exc:
            raise ValueError('An invalid filter was passed.') from exc

        query = """

                SELECT doi,
                normalized_publisher,
                normalized_journal,
                normalized_received,
                normalized_accepted,
                normalized_published,
                CASE WHEN normalized_accepted >= normalized_received
                     THEN CAST(JULIANDAY(normalized_accepted) - JULIANDAY(normalized_received) as INT) END,
                CASE WHEN normalized_published >= normalized_received
                     THEN CAST(JULIANDAY(normalized_published) - JULIANDAY(normalized_received) as INT) END,
                CASE WHEN normalized_published >= normalized_accepted
                     THEN CAST(JULIANDAY(normalized_published) - JULIANDAY(normalized_accepted) as INT) END"""

        if get_title:
            query += ',\ntitle'
        else:
            query += ',\nNULL'

        if get_publication_type:
            query += ',\npublication_type'
        else:
            query += ',\nNULL'

        if get_no_of_authors:
            query += ',\nno_of_authors'
        else:
            query += ',\nNULL'

        if get_author_names:
            query += ',\nauthor_names'
        else:
            query += ',\nNULL'

        if get_affiliations:
            query += ',\naffiliations'
        else:
            query += ',\nNULL'

        query += ',\nwarnings'

        query += '\nFROM pub\n'

        query += add_2_query

        query += """
                ORDER BY normalized_publisher,
                normalized_journal,
                normalized_received,
                normalized_accepted
                """

        self._cur.execute(query, args_query)

        filtered_pubs = list(map(FilteredPub._make, self._cur.fetchall()))
        filtered_pubs = [publication._replace(
            author_names=(json.loads(publication.author_names)
                          if publication.author_names else None),
            affiliations=(json.loads(publication.affiliations)
                          if publication.affiliations else None),
            warnings=json.loads(publication.warnings or '[]'),
        ) for publication in filtered_pubs]

        return filtered_pubs

    def _prepare_filters(self, **kwargs):
        """
        Used by ``self.filter_pjt()`` to build a dict with default values

        The keyword arguments are the same as in ``self.filter_pjt()``

        Returns
        -------
        where_query : str
            String to be added to the filter_pjt() query
        args_query : list
            Arguments to pass to the filter_pjt() query

        Raises
        ------
        ValueError
            An error if an invalid data type is passed to filter_pjt()

        """

        clauses = []
        arguments = []

        list_filters = {
            'normalized_publisher': 'normalized_publisher',
            'normalized_journal': 'normalized_journal',
            'publication_type': 'publication_type',
        }
        for key, column in list_filters.items():
            if key not in kwargs:
                continue
            values = kwargs[key]
            if not _utils.is_list_of_str(values):
                raise ValueError(f'Invalid {key} filter; must be strings.')
            if isinstance(values, str):
                values = [values]
            placeholders = ', '.join('?' for _ in values)
            clauses.append(f'{column} IN ({placeholders})')
            arguments.extend(values)

        for date_name in ('received', 'accepted', 'published'):
            minimum_key = f'min_{date_name}'
            maximum_key = f'max_{date_name}'
            minimum = (date_utils.normalize_date_2iso(kwargs[minimum_key])
                       if minimum_key in kwargs else None)
            maximum = (date_utils.normalize_date_2iso(
                           kwargs[maximum_key], end=True)
                       if maximum_key in kwargs else None)
            if minimum and maximum and minimum > maximum:
                raise ValueError(f'Inverted {date_name} date range.')
            if minimum:
                clauses.append(f'normalized_{date_name} >= ?')
                arguments.append(minimum)
            if maximum:
                clauses.append(f'normalized_{date_name} <= ?')
                arguments.append(maximum)

        where_query = ('\nWHERE ' + ' AND '.join(clauses)) if clauses else ''
        return where_query, arguments
