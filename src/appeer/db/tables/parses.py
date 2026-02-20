"""Handles the ``parses`` table in ``jobs.db``"""

from appeer.db.tables.action_table import ActionTable
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.parse import parse_reports as reports

from appeer.general import utils as _utils

class Parses(ActionTable,
        name='parses',
        columns=get_registered_tables()['parses']):
    """
    Handles the ``parses`` table

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
    def uncommitted(self):
        """
        Returns all uncommitted parses (status='X', committed='F')

        Returns
        -------
        uncommitted_parses : list of appeer.db.tables.parses._Parse
            Unparsed parses

        """

        uncommitted_parses = self._search_table(
                status='X', committed='F', success='T')

        return uncommitted_parses

    @property
    def uncommitted_summary(self):
        """
        Formatted summary of all uncommitted parses

        Returns
        -------
        _summary : str
            Summary of all uncommitted parses

        """

        _summary = reports.uncommitted_parses(parses=self)

        return _summary

    def add_entry(self, **kwargs):
        """
        Initializes an entry for a parse

        Keyword Arguments
        -----------------
        label : str
            Label of the parse job
        action_index : int
            Index of the action within the job
        scrape_label : str
            Label of the scrape job that the input file corresponds to
                (can be None if the input file does not come from a scrape job)
        scrape_action_index : int
            Index of the scrape action that the input file corresponds to
                (can be None if the input file does not come from a scrape job)
        date : str
            Date and time of the parse
        input_file : str
            Path to the file to be parsed

        """

        data = ({
            'label': kwargs['label'],
            'action_index': kwargs['action_index'],
            'scrape_label': kwargs['scrape_label'],
            'scrape_action_index': kwargs['scrape_action_index'],
            'date': kwargs['date'],
            'input_file': kwargs['input_file'],
            'doi': None,
            'publisher': None,
            'journal': None,
            'title': None,
            'publication_type': None,
            'no_of_authors': None,
            'author_names': None,
            'affiliations': None,
            'received': None,
            'accepted': None,
            'published': None,
            'normalized_received': None,
            'normalized_accepted': None,
            'normalized_published': None,
            'normalized_publisher': None,
            'normalized_journal': None,
            'parser': None,
            'success': 'F',
            'status': 'W',
            'committed': 'F'
            })

        self._sanity_check()

        colons_values = ', '.join([':' + key for key in data])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        self._cur.execute(add_query, data)

        self._con.commit()

    def update_entry(self, **kwargs): #pylint:disable=too-many-statements, too-many-branches
        """
        Given a ``label`` and ``action_index``, updates the corresponding 
            ``column_name`` value with ``new_value`` in the ``parse`` table

        ``column_name`` must be in 

            ('date',
            'doi', 'publisher', 'journal',
            'title', 'publication_type',
            'no_of_authors', 'author_names', 'affiliations',
            'received', 'accepted', 'published',
            'normalized_received',
            'normalized_accepted',
            'normalized_published',
            'normalized_publisher', 'normalized_journal',
            'parser', 'success', 'status', 'committed'
            )

        Keyword Arguments
        -----------------
        label : str
            Label of the job that the parse belongs to
        action_index : int
            Index of the action within the job
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
                    raise ValueError(f'Cannot update the "parses" table. Invalid date={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET date = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'doi':

                if not _utils.check_doi_format(new_value):
                    raise ValueError(f'Cannot update the "parses" table. Invalid doi={new_value} given; must be valid DOI format')

                self._cur.execute("""
                UPDATE parses SET doi = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'publisher':

                # TODO: explicit publisher check should be implemented
                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid publisher={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET publisher = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'journal':

                # TODO: explicit journal check should be implemented
                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid journal={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET journal = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'title':

                # TODO: explicit journal check should be implemented
                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid title={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET title = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'publication_type':

                # TODO: explicit check of known article types should be implemented
                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid publication_type={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET publication_type = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'no_of_authors':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "parses" table. Invalid no_of_authors={new_value} given; must be an integer')

                if not new_value > 0:
                    raise ValueError(f'Cannot update the "parses" table. Invalid no_of_authors={new_value} given; must be a positive integer')

                self._cur.execute("""
                UPDATE parses SET no_of_authors = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'author_names':

                if not isinstance(new_value, list):
                    raise ValueError(f'Cannot update the "parses" table. Invalid author_names={new_value} given; must be a list')

                if not all(_utils.is_list_of_str(aff) for aff in new_value):
                    raise ValueError(f'Cannot update the "parses" table. Invalid author_names={new_value} given; each entry must be list of strings')

                new_value = [[name] for name in new_value]
                authors_str = _utils.aff_list2str(new_value)

                self._cur.execute("""
                UPDATE parses SET author_names = ? WHERE label = ? AND action_index = ?
                """, (authors_str, label, action_index))

                self._con.commit()

            case 'affiliations':

                if not isinstance(new_value, list):
                    raise ValueError(f'Cannot update the "parses" table. Invalid affiliations={new_value} given; must be a list')

                if not all(_utils.is_list_of_str(aff) for aff in new_value):
                    raise ValueError(f'Cannot update the "parses" table. Invalid affiliations={new_value} given; each entry must be list of strings')

                affs_str = _utils.aff_list2str(new_value)

                self._cur.execute("""
                UPDATE parses SET affiliations = ? WHERE label = ? AND action_index = ?
                """, (affs_str, label, action_index))

                self._con.commit()

            case 'received':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid received={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET received = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'accepted':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid accepted={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET accepted = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'published':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid published={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET published = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'normalized_received':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid normalized_received={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET normalized_received = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'normalized_accepted':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid normalized_accepted={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET normalized_accepted = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'normalized_published':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid normalized_published={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET normalized_published = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'normalized_publisher':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid normalized_publisher={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET normalized_publisher = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'normalized_journal':

                if not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid normalized_journal={new_value} given; must be a string')

                self._cur.execute("""
                UPDATE parses SET normalized_journal = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'parser':

                #TODO: explicit parser check should be implemented
                if new_value and not isinstance(new_value, str):
                    raise ValueError(f'Cannot update the "parses" table. Invalid parser={new_value} given; must be a string.')

                self._cur.execute("""
                UPDATE parses SET parser = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'success':

                if not new_value in ('T', 'F'):
                    raise ValueError(f'Cannot update the "parses" table. Invalid success={new_value} given; must be one of ("T", "F").')

                self._cur.execute("""
                UPDATE parses SET success = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'status':

                if not new_value in ('I', 'W', 'R', 'E', 'X'):
                    raise ValueError(f'Cannot update the "parses" table. Invalid status={new_value} given; must be one of ("I", "W", "R", "E", "X").')

                self._cur.execute("""
                UPDATE parses SET status = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case 'committed':

                if new_value not in ('T', 'F'):
                    raise ValueError(f'Cannot update the "parses" table. Invalid parsed={new_value} given; must be "T" or "F".')

                self._cur.execute("""
                UPDATE parses SET committed = ? WHERE label = ? AND action_index = ?
                """, (new_value, label, action_index))

                self._con.commit()

            case _:

                self._con.close()
                raise ValueError(f'Cannot update the "parses" table. Invalid column name "{column_name}" given.')

        self._con.close()
