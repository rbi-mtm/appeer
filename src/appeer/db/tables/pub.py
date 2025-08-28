"""Handles the ``pub`` table in ``pub.db``"""

import sqlite3
from collections import namedtuple

import click

from appeer.db.tables.table import Table
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.parse.default_metadata import default_metadata
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
        'affiliations'],
        defaults=[None, None, None, None]
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

    def initialize_table(self):
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

        columns_commas = ', '.join(self._columns)
        initialize_query = f'CREATE TABLE {self._name}({columns_commas}, PRIMARY KEY(doi COLLATE NOCASE))' #pylint:disable=line-too-long

        self._cur.execute(initialize_query)
        self._con.commit()

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

        colons_values = ', '.join([':' + meta for meta in default_metadata()])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        try:

            self._cur.execute(add_query, kwargs)
            self._con.commit()

            inserted = True

        except sqlite3.IntegrityError:

            duplicate = True

            if overwrite:

                replace_query =\
                        f'REPLACE INTO {self._name} VALUES({colons_values})'

                self._cur.execute(replace_query, kwargs)
                self._con.commit()

                inserted = True

            else:
                pass

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

    def _prepare_filters(self, **kwargs): #pylint: disable=too-many-statements, too-many-branches
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

        add_2_query = ''
        args_query = []

        where_or_and = '\nWHERE'

        # Publishers filter
        try:

            if not _utils.is_list_of_str(kwargs['normalized_publisher']):
                raise ValueError('Invalid publishers filter; must be a (list of) string(s).')

            if isinstance(kwargs['normalized_publisher'], str):
                kwargs['normalized_publisher'] = [kwargs['normalized_publisher']]

            question_marks = ", ".join(['?'] * len(kwargs['normalized_publisher']))

            add_2_query += f'{where_or_and} normalized_publisher IN ({question_marks})'
            args_query.extend(kwargs['normalized_publisher'])

            where_or_and = '\nAND'

        except KeyError:
            pass

        # Journals filter
        try:

            if not _utils.is_list_of_str(kwargs['normalized_journal']):
                raise ValueError('Invalid journals filter; must be a (list of) string(s).')

            if isinstance(kwargs['normalized_journal'], str):
                kwargs['normalized_journal'] = [kwargs['normalized_journal']]

            question_marks = ", ".join(['?'] * len(kwargs['normalized_journal']))

            add_2_query += f'{where_or_and} normalized_journal IN ({question_marks})'
            args_query.extend(kwargs['normalized_journal'])

            where_or_and = '\nAND'

        except KeyError:
            pass

        # Minimum received date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['min_received'])

                add_2_query += f'{where_or_and} normalized_received >= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid minimum received date.') from exc

        except KeyError:
            pass

        # Maximum received date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['max_received'])

                add_2_query += f'{where_or_and} normalized_received <= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid maximum received date.') from exc

        except KeyError:
            pass

        # Minimum accepted date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['min_accepted'])

                add_2_query += f'{where_or_and} normalized_accepted >= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid minimum accepted date.') from exc

        except KeyError:
            pass

        # Maximum accepted date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['max_accepted'])

                add_2_query += f'{where_or_and} normalized_accepted <= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid maximum accepted date.') from exc

        except KeyError:
            pass

        # Minimum published date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['min_published'])

                add_2_query += f'{where_or_and} normalized_published >= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid minimum published date.') from exc

        except KeyError:
            pass

        # Maximum published date filter
        try:

            try:

                normalized_date = date_utils.normalize_date_2iso(kwargs['max_published'])

                add_2_query += f'{where_or_and} normalized_published <= ?'
                args_query.extend([normalized_date])

                where_or_and = '\nAND'

            except ValueError as exc:
                raise ValueError('Invalid maximum published date.') from exc

        except KeyError:
            pass

        # Publication type filter (TODO, unstable)
        try:

            if not _utils.is_list_of_str(kwargs['publication_type']):
                raise ValueError('Invalid publication type filter; must be a (list of) string(s).')

            if isinstance(kwargs['publication_type'], str):
                kwargs['publication_type'] = [kwargs['publication_type']]

            question_marks = ", ".join(['?'] * len(kwargs['publication_type']))

            add_2_query += f'{where_or_and} publication_type IN ({question_marks})'
            args_query.extend(kwargs['publication_type'])

        except KeyError:
            pass

        return add_2_query, args_query
