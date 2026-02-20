"""Handles the ``commits`` table in ``jobs.db``"""

from appeer.db.tables.action_table import ActionTable
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.general import utils as _utils

class Commits(ActionTable,
        name='commits',
        columns=get_registered_tables()['commits']):
    """
    Handles the ``commits`` table

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

    def add_entry(self, **kwargs):
        """
        Initializes an entry for a commit

        Keyword Arguments
        -----------------
        label : str
            Label of the commit job
        action_index : int
            Index of the action within the job
        parse_label : str
            Label of the parse job that the metadata corresponds to
        parse_action_index : int
            Index of the parse action that the metadata corresponds to
        date : str
            Date and time of the commit

        """

        data = ({
            'label': kwargs['label'],
            'action_index': kwargs['action_index'],
            'parse_label': kwargs['parse_label'],
            'parse_action_index': kwargs['parse_action_index'],
            'date': kwargs['date'],
            'doi': kwargs['doi'],
            'publisher': kwargs['publisher'],
            'journal': kwargs['journal'],
            'title': kwargs['title'],
            'publication_type': kwargs['publication_type'],
            'no_of_authors': kwargs['no_of_authors'],
            'author_names': kwargs['author_names'],
            'affiliations': kwargs['affiliations'],
            'received': kwargs['received'],
            'accepted': kwargs['accepted'],
            'published': kwargs['published'],
            'normalized_received': kwargs['normalized_received'],
            'normalized_accepted': kwargs['normalized_accepted'],
            'normalized_published': kwargs['normalized_published'],
            'normalized_publisher': kwargs['normalized_publisher'],
            'normalized_journal': kwargs['normalized_journal'],
            'success': 'F',
            'status': 'W',
            'passed': 'F',
            'duplicate': 'F'
            })

        self._sanity_check()

        colons_values = ', '.join([':' + key for key in data])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        self._cur.execute(add_query, data)
        self._con.commit()

    def update_entry(self, **kwargs):
        """
        Given a ``label`` and ``action_index``, updates the corresponding
            ``column_name`` value with ``new_value`` in the ``parse`` table

        ``column_name`` must be in ('date', 'success', 'status',
                                    'passed', 'duplicate')

        Keyword Arguments
        -----------------
        label : str
            Label of the job that the parse belongs to
        action_index : int
            Index of the URL in the input
        column_name : str
            Name of the column whose value is being updated
        new_value : str : int
            New value of the given column

        """

        self._sanity_check()

        label = kwargs['label']
        action_index = kwargs['action_index']
        column_name = kwargs['column_name']
        new_value = kwargs['new_value']

        match column_name:

            case 'date':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "commits" table. Invalid date={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE commits SET date = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'success':

                if not new_value in ('T', 'F'):
                    raise ValueError(f'Cannot update the "commits" table. Invalid success={new_value} given; must be one of ("T", "F").')

                self._cur.execute("""
                UPDATE commits SET success = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'status':

                if not new_value in ('I', 'W', 'R', 'E', 'X'):
                    raise ValueError(f'Cannot update the "commits" table. Invalid status={new_value} given; must be one of ("I", "W", "R", "E", "X").')

                self._cur.execute("""
                UPDATE commits SET status = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'passed':

                if new_value not in ('T', 'F'):
                    raise ValueError(f'Cannot update the "commits" table. Invalid passed={new_value} given; must be "T" or "F".')

                self._cur.execute("""
                UPDATE commits SET passed = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'duplicate':

                if new_value not in ('T', 'F'):
                    raise ValueError(f'Cannot update the "commits" table. Invalid duplicate={new_value} given; must be "T" or "F".')

                self._cur.execute("""
                UPDATE commits SET duplicate = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case _:

                self._con.close()
                raise ValueError(f'Cannot update the "commits" table. Invalid column name "{column_name}" given.')

        self._con.close()
