"""Analyze results obtained using PubReSearcher"""

from collections import Counter

import numpy as np

import appeer.general.utils as _utils

from appeer.parse.parsers import date_utils as _date_utils

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


    @property
    def basic_search_results(self):
        """
        Get a basic summary of the search results

        Returns
        -------
        _basic_search_results : dict
            Dictionary of basic search results

        """

        if self._filtered_pubs:

            no_of_pubs = len(self._filtered_pubs)

            publishers = Counter(pub.publisher for pub in self._filtered_pubs)
            journals = Counter(pub.journal for pub in self._filtered_pubs)

            _basic_search_results = {
                    'no_of_pubs': no_of_pubs,
                    'publishers': publishers,
                    'no_of_publishers': len(publishers),
                    'journals': journals,
                    'no_of_journals': len(journals),
                    }


            _basic_search_results['min_received'] =\
                    _date_utils.earliest_date([pub.normalized_received
                    for pub in self._filtered_pubs])

            _basic_search_results['max_received'] =\
                    _date_utils.latest_date([pub.normalized_received
                    for pub in self._filtered_pubs])

            _basic_search_results['min_accepted'] =\
                    _date_utils.earliest_date([pub.normalized_accepted
                    for pub in self._filtered_pubs])

            _basic_search_results['max_accepted'] =\
                    _date_utils.latest_date([pub.normalized_accepted
                    for pub in self._filtered_pubs])

            _basic_search_results['min_published'] =\
                    _date_utils.earliest_date([pub.normalized_published
                    for pub in self._filtered_pubs])

            _basic_search_results['max_published'] =\
                    _date_utils.latest_date([pub.normalized_published
                    for pub in self._filtered_pubs])


            _basic_search_results['average_ra'] =\
                    np.average([pub.received_2_accepted
                    for pub in self._filtered_pubs])

            _basic_search_results['average_rp'] =\
                    np.average([pub.received_2_published
                    for pub in self._filtered_pubs])

            _basic_search_results['average_ap'] =\
                    np.average([pub.accepted_2_published
                    for pub in self._filtered_pubs])

        else:
            _basic_search_results = {}


        return _basic_search_results
