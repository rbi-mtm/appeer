"""Interface to the pub.db database"""

from appeer.db.db import DB

class PubDB(DB, tables=['pub']):
    """
    Interface to the pub.db database

    """

    def __init__(self, read_only=False, db_path=None):
        """
        If the pub database exists, establishes a connection and a cursor.

        Parameters
        ----------
        read_only : bool
            If True, open the database in read-only mode

        """

        super().__init__(db_type='pub', read_only=read_only, db_path=db_path)
