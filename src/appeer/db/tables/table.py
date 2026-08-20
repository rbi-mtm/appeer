"""Base abstract class for handling tables in sqlite3 databases"""

import abc
import inspect

from collections import namedtuple

from appeer.db.tables.registered_tables import (
    check_column,
    get_table_schemas,
    sanity_check,
)

class Table(abc.ABC):
    """
    Base abstract class for handling tables in the sqlite3 databases

    """

    def __init_subclass__(cls, name=None, columns=None):
        """
        Ensures that every Table subclass defines ``name`` and ``columns``

        Abstract subclasses do not have to define ``name and columns``

        Parameters
        ----------
        name : str
            Name of the table in the database
        columns : list
            List of column names

        """

        if inspect.isabstract(cls):
            return

        if name and columns:

            if not isinstance(name, str):
                raise TypeError('Table name must be a string.')

            if not isinstance(columns, list):
                raise TypeError(f'Columns of table {name} must be given as a list of strings.')

            for column in columns:
                if not isinstance(column, str):
                    raise TypeError(f'Non-string value given for a column in {columns} in table {name}.')

            sanity_check(name=name, columns=columns)

            cls._name = name
            cls._columns = columns

            return

        raise TypeError('"name" and "columns" must be supplied as class named arguments')

    def __init__(self, connection):
        """
        Establishes a connection between the table and corresponding database

        Parameters
        ----------
        connection : sqlite3.Connection
            Connection to the database to which the table belongs to

        """

        self._sanity_check()

        self._con = connection
        self._cur = self._con.cursor()

        self._row_tuple = namedtuple(f'_{self._name[:-1]}', self._columns)

    def _sanity_check(self):
        """
        Check if the table name and columns are allowed

        """

        sanity_check(name=self._name, columns=self._columns)

    def _rows(self, rows):
        """
        Convert fetched rows without changing connection-global row state.

        """

        return [self._row_tuple(*row) for row in rows]

    def initialize_table(self, commit=True):
        """
        Initializes an empty table

        """

        self._sanity_check()

        columns_commas = ', '.join(get_table_schemas()[self._name])
        initialize_query = f'CREATE TABLE {self._name}({columns_commas})'

        self._cur.execute(initialize_query)
        if commit:
            self._con.commit()

    @property
    def entries(self):
        """
        Gets all entries in the table

        """

        entries_query = f'SELECT * FROM {self._name}'
        self._cur.execute(entries_query)

        all_entries = self._rows(self._cur.fetchall())

        return all_entries

    @abc.abstractmethod
    def add_entry(self, **kwargs):
        """
        Initializes an entry

        """

    @abc.abstractmethod
    def update_entry(self, **kwargs):
        """
        Updates an entry

        """

    @abc.abstractmethod
    def delete_entry(self, **kwargs):
        """
        Deletes an entry

        """

    def _search_table(self, and_or=None, contains=None, **kwargs): #pylint:disable=too-many-branches
        """
        Performs simple table searches

        Returns rows from the table with (column, value) pairs
            (not) equal to (key, value) in ``kwargs``
        
        Parameters
        ----------
        and_or : list of str
            List of 'AND'/'OR' values for combining (column, value) pairs;
                must be of length ``len(kwargs) - 1``;
                defaults to a list of 'AND'

        contains : list of bool
            If True, search the table for rows containing
                (column, value) pairs;
            if False, search for rows NOT containing
                (column, value) pairs
            
        kwargs : dict
            The table is searched for rows (not) containing
                (column, value) pairs defined by (key, value) in kwargs

        Returns
        -------
        search_result : namedtuple
            The row written to the named tuple corresponding to the table

        """

        self._sanity_check()

        if and_or is None:
            and_or = ['AND'] * (len(kwargs) - 1)

        if len(and_or) != len(kwargs) - 1:
            raise ValueError('The length of the "and_or" list must be equal to the given number of columns - 1.')

        if contains is None:
            contains = [True] * len(kwargs)

        if len(contains) != len(kwargs):
            raise ValueError('The length of the "contains" list must be of the same length as the given number of columns.')

        query = f'SELECT * from {self._name} WHERE '

        params = ()

        for i, (column, value) in enumerate(kwargs.items()):

            check_column(name=f'{self._name}', column=column)

            if contains[i] is True:
                equality = '='

            elif contains[i] is False:
                equality = '!='

            else:
                raise ValueError('The "contains" parameter must be a list of bools.')

            if i > 0:

                if and_or[i - 1] not in ('AND', 'OR'):
                    raise PermissionError(f'Invalid value {and_or[i - 1]} found in the and_or list.')

                query += (f' {and_or[i - 1]} ')

            query += '('

            if not isinstance(value, list):
                value = [value]

            for j, val in enumerate(value):

                if j > 0:
                    query += ' OR '

                query += f'{column} {equality} ?'

                params += (val,)

            query += ')'

        self._cur.execute(query, params)
        search_result = self._rows(self._cur.fetchall())

        return search_result
