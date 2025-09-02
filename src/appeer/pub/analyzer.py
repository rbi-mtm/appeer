"""Analyze results obtained using PubReSearcher"""

import appeer.general.utils as _utils

class PubAnalyzer:
    """
    Analyze results (usually) obtained using PubReSearcher

    """

    def __init__(self, filtered_pubs):
        """
        Initialize ``PubAnalyzer`` using ``filtered_pubs``

            ``filtered_pubs`` are usually obtained by PubReSearcher

        Parameters
        ----------
        filtered_pubs : list of appeer.db.tables.pub.FilteredPub
            List of ``FilteredPub`` (usually obtained from PubReSearcher)

        """

        self.load_data(filtered_pubs)


    def load_data(self, filtered_pubs):
        """
        Loads data to self._filtered_pubs

        Parameters
        ----------
        filtered_pubs : list of appeer.db.tables.pub.FilteredPub
            List of ``FilteredPub`` (obtained from PubReSearcher.search_pub)

        """

        if filtered_pubs:
            _utils.check_FilteredPub_type(filtered_pubs)

        else:
            filtered_pubs = []

        self._filtered_pubs = filtered_pubs
