"""Handles the ``commit_jobs`` table in ``jobs.db``"""

from appeer.db.tables.job_table import JobTable
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.commit import commit_reports as reports

class CommitJobs(JobTable,
              name='commit_jobs',
              columns=get_registered_tables()['commit_jobs']):
    """
    Handles the ``commit_jobs`` table

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

        Parameters
        ----------
        connection : sqlite3.Connection
            Connection to the database to which the table belongs to

        """

        super().__init__(connection=connection)

    @property
    def summary(self):
        """
        Get a formatted summary of all commit jobs in the table

        Returns
        -------
        _summary : str
            Formatted summary of all commit jobs in the table

        """

        _summary = reports.commit_jobs_summary(self)

        return _summary

    def add_entry(self, **kwargs):
        """
        Initializes an entry for a commit job

        Keyword Arguments
        -----------------
        label : str
            Label of the commit job
        date : str
            Date on which the commit job was initialized
        description : str
            Description of the commit job
        log : str
            Path to the log of the commit job
        mode : str
            Commit mode. Must be in ('A', 'E', 'P')

        """

        if kwargs['mode'] not in ('A', 'E', 'P'):
            raise ValueError(f'Cannot add entry to the "commit_jobs" table; invalid mode {kwargs["mode"]} inputted.')

        data = ({
            'label': kwargs['label'],
            'date': kwargs['date'],
            'description': kwargs['description'],
            'log': kwargs['log_path'],
            'mode': kwargs['mode'],
            'job_status': 'I',
            'job_step': 0,
            'job_successes': 0,
            'job_fails': 0,
            'job_passes': 0,
            'job_duplicates': 0,
            'no_of_publications': 0,
            })


        self._sanity_check()

        colons_values = ', '.join([':' + key for key in data])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        self._cur.execute(add_query, data)
        self._con.commit()

    def update_entry(self, **kwargs): #pylint: disable=too-many-branches
        """
        Updates an entry in the ``commit_jobs`` table

        Given a ``label``, updates the corresponding ``column_name``
            with ``new_value`` in the ``commit_jobs`` table

        ``column_name`` must be in
            ('job_status', 'job_step', 'job_successes', 'job_fails',
            'no_of_publications')

        Keyword Arguments
        -----------------
        label : str
            Label of the commit job that is being updated
        column_name : str
            Name of the column whose value is being updated
        new_value : str : int
            New value of the given column

        """

        self._sanity_check()

        label = kwargs['label']
        column_name = kwargs['column_name']
        new_value = kwargs['new_value']

        match column_name:

            case 'job_status':

                if new_value not in ('I', 'W', 'R', 'X', 'E'):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_status={new_value} given; must be "I", "R", "X" or "E".')

                self._cur.execute("""
                UPDATE commit_jobs SET job_status = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'no_of_publications':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_publications={new_value} given; must be a positive integer.')

                if not new_value > 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_publications={new_value} given; must be a positive integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET no_of_publications = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_step':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_step={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_step={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET job_step = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_successes':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_success={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_success={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET job_successes = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_fails':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_fails={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid no_of_fails={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET job_fails = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_passes':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_passes={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_passes={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET job_passes = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_duplicates':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_duplicates={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the "commit_jobs" table. Invalid job_duplicates={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE commit_jobs SET job_duplicates = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case _:

                raise ValueError(f'Cannot update the "commit_jobs" table. Invalid column name "{column_name}" given.')
