"""Handles the ``scrapes`` table in ``jobs.db``"""

from appeer.db.tables.action_table import ActionTable
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.scrape import scrape_reports as reports

class Scrapes(ActionTable,
        name='scrapes',
        columns=get_registered_tables()['scrapes']):
    """
    Handles the ``scrapes`` table

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

    @property
    def unparsed(self):
        """
        Returns all unparsed scrapes (status='X', parsed='F', success='T')

        Returns
        -------
        unparsed_scrapes : list of appeer.db.tables.scrapes._Scrape
            Unparsed scrapes

        """

        unparsed_scrapes = self._search_table(
                status='X', parsed='F', success='T')

        return unparsed_scrapes

    @property
    def unparsed_summary(self):
        """
        Formatted summary of all unparsed scrapes

        Returns
        -------
        _summary : str
            Summary of all unparsed scrapes

        """

        _summary = reports.unparsed_scrapes(scrapes=self)

        return _summary

    def add_entry(self, **kwargs):
        """
        Initializes an entry for a scrape

        Keyword Arguments
        -----------------
        label : str
            Label of the scrape job
        action_index : int
            Index of the URL in the input
        date : str
            Date and time of the scrape
        url : str
            Inputted URL
        journal : str
            Internal journal code of the URL
        strategy : str
            Internal code of the strategy used for scraping
        method : str
            Internal name of the method used for scraping

        """

        data = ({
            'label': kwargs['label'],
            'action_index': kwargs['action_index'],
            'date': kwargs['date'],
            'url': kwargs['url'],
            'journal': kwargs['journal'],
            'strategy': kwargs['strategy'],
            'method': kwargs['method'],
            'success': 'F',
            'status': 'W',
            'out_file': 'no_file',
            'parsed': 'F'
            })

        self._sanity_check()

        colons_values = ', '.join([':' + key for key in data])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        self._cur.execute(add_query, data)
        self._con.commit()

    def update_entry(self, **kwargs):
        """
        Given a ``label`` and ``action_index``, updates the corresponding 
            ``column_name`` value with ``new_value`` in the ``scrape`` table

        ``column_name`` must be in ('date', 'journal', 'strategy', 'status',
            'success', 'out_file', 'parsed')

        Keyword Arguments
        -----------------
        label : str
            Label of the job that the scrape belongs to
        action_index : int
            Index of the URL in the input
        column_name : str
            Name of the column whose value is being updated
        new_value : str | int
            New value of the given column

        """

        self._sanity_check()

        label = kwargs['label']
        action_index = kwargs['action_index']
        column_name = kwargs['column_name']
        new_value = kwargs['new_value']

        match column_name:

            case 'strategy':

                # TODO: strategies in the ScrapePlan will be revised
                # if False is left as a placeholder
                if False:
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid strategy={new_value} given; must be ...')

                else:

                    self._cur.execute("""
                    UPDATE scrapes SET strategy = ? WHERE label = ? AND action_index = ?
                    """, (new_value, label, action_index))

                    self._con.commit()

            case 'method':

                # TODO: strategies in the ScrapePlan will be revised
                # if False is left as a placeholder
                if False:
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid method={new_value} given; must be ...')

                else:

                    self._cur.execute("""
                    UPDATE scrapes SET method = ? WHERE label = ? AND action_index = ?
                    """, (new_value, label, action_index))

                    self._con.commit()

            case 'journal':

                # TODO: journals in the ScrapePlan will be revised
                # if False is left as a placeholder
                if False:
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid journal={new_value} given; must be ...')

                else:

                    self._cur.execute("""
                    UPDATE scrapes SET journal = ? WHERE label = ? AND action_index = ?
                    """, (new_value, label, action_index))

                    self._con.commit()

            case 'success':

                if not new_value in ('T', 'F'):
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid success={new_value} given; must be one of ("T", "F").')

                self._cur.execute("""
                UPDATE scrapes SET success = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'status':

                if not new_value in ('I', 'W', 'R', 'E', 'X'):
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid status={new_value} given; must be one of ("I", "W", "R", "E", "X").')

                self._cur.execute("""
                UPDATE scrapes SET status = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'out_file':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid out_file={new_value} given; must be a string.')

                self._cur.execute("""
                UPDATE scrapes SET out_file = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'date':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid date={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE scrapes SET date = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'parsed':

                if new_value not in ('T', 'F'):
                    raise ValueError(f'Cannot update the "scrapes" table. Invalid parsed={new_value} given; must be "T" or "F".')

                self._cur.execute("""
                UPDATE scrapes SET parsed = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case _:

                raise ValueError(f'Cannot update the "scrapes" table. Invalid column name "{column_name}" given.')
