"""Handles the ``scrape_jobs`` table in ``jobs.db``"""

from appeer.db.tables.job_table import JobTable
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.scrape import scrape_reports as reports


class ScrapeJobs(JobTable,
        name='scrape_jobs',
        columns=get_registered_tables()['scrape_jobs']):
    """
    Handles the ``scrape_jobs`` table

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
        Get a formatted summary of all scrape jobs in the table

        Returns
        -------
        _summary : str
            Formatted summary of all scrape jobs in the table

        """

        _summary = reports.scrape_jobs_summary(self)

        return _summary

    @property
    def unparsed(self):
        """
        Returns all unparsed scrape jobs (status='X', job_parsed='F')

        Returns
        -------
        unparsed_scrape_jobs : list of appeer.db.tables.scrape_jobs._ScrapeJobs
            Unparsed scrape jobs

        """

        unparsed_scrape_jobs = self._search_table(
                job_status='X', job_parsed='F')

        return unparsed_scrape_jobs

    @property
    def executed(self):
        """
        Returns all executed scrape jobs (status='X')

        Returns
        -------
        executed_scrape_jobs : list of appeer.db.tables.scrape_jobs._ScrapeJobs
            Executed scrape jobs

        """

        executed_scrape_jobs = self._search_table(job_status='X')

        return executed_scrape_jobs

    def add_entry(self, **kwargs):
        """
        Initializes an entry in the scrape_jobs table

        Keyword Arguments
        -----------------
        label : str
            Label of the scrape job
        description : str
            Description of the scrape job
        log_path : str
            Path to the log of the scrape job
        download_directory : str
            Path to the directory where the data is being downloaded
        zip_file : str
            Path to the output ZIP file of the scrape job
        date : str
            Date on which the scrape job was initialized

        """

        data = ({
            'label': kwargs['label'],
            'date': kwargs['date'],
            'description': kwargs['description'],
            'log': kwargs['log_path'],
            'download_directory': kwargs['download_directory'],
            'zip_file': kwargs['zip_file'],
            'job_status': 'I',
            'job_step': 0,
            'job_successes': 0,
            'job_fails': 0,
            'no_of_publications': 0,
            'job_parsed': 'F'
            })

        self._sanity_check()

        colons_values = ', '.join([':' + key for key in data])

        add_query = f'INSERT INTO {self._name} VALUES({colons_values})'

        self._cur.execute(add_query, data)
        self._con.commit()

    def update_entry(self, **kwargs):
        """
        Updates an entry in the scrape_jobs table

        Given a ``label``, updates the corresponding ``column_name``
            with ``new_value`` in the ``scrape_jobs`` table

        ``column_name`` must be in
            ('job_status', 'job_step', 'job_successes', 'job_fails',
            'no_of publications', 'job_parsed')

        Keyword Arguments
        -----------------
        label : str
            Label of the scrape job that is being updated
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
                    raise ValueError(f'Cannot update the scrape database. Invalid job_status={new_value} given; must be "I", "R", "X" or "E".')

                self._cur.execute("""
                UPDATE scrape_jobs SET job_status = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'no_of_publications':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_publications={new_value} given; must be a positive integer.')

                if not new_value > 0:
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_publications={new_value} given; must be a positive integer.')

                self._cur.execute("""
                UPDATE scrape_jobs SET no_of_publications = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_step':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the scrape database. Invalid job_step={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the scrape database. Invalid job_step={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE scrape_jobs SET job_step = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_successes':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_success={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_success={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE scrape_jobs SET job_successes = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_fails':

                if not isinstance(new_value, int):
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_fails={new_value} given; must be an integer.')

                if not new_value >= 0:
                    raise ValueError(f'Cannot update the scrape database. Invalid no_of_fails={new_value} given; must be a non-negative integer.')

                self._cur.execute("""
                UPDATE scrape_jobs SET job_fails = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case 'job_parsed':

                if new_value not in ('T', 'F'):
                    raise ValueError(f'Cannot update the scrape database. Invalid job_parsed={new_value} given; must be "T" or "F".')

                self._cur.execute("""
                UPDATE scrape_jobs SET job_parsed = ? WHERE label = ?
                """, (new_value, label))

                self._con.commit()

            case _:

                raise ValueError(f'Cannot update the scrape database. Invalid column name "{column_name}" given.')
