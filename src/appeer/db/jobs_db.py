"""Handles the jobs database, which includes scrape, parse and commit jobs"""

from appeer.db.db import DB

class JobsDB(DB, tables=[
        'scrape_jobs',
        'scrapes',
        'parse_jobs',
        'parses',
        'commit_jobs',
        'commits'
    ]):
    """
    Handles the ``jobs.db`` database

    """

    def __init__(self, read_only=False, db_path=None):
        """
        If the jobs database exists, establishes a connection and a cursor

        Parameters
        ----------
        read_only : bool
            If True, open the database in read-only mode

        """

        super().__init__(db_type='jobs', read_only=read_only, db_path=db_path)
