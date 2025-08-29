"""Filter, plot, analyze results from pub.db"""

from appeer.db.pub_db import PubDB

class PubReSearcher:
    """
    Filter, plot, analyze results from pub.db

    """

    def __init__(self):
        """
        Connects to the pub.db database

        """

        self._pub = PubDB().pub

        self.filtered_pubs = []


    def search_pub(self,
                   get_title=False,
                   get_publication_type=False,
                   get_no_of_authors=False,
                   get_affiliations=False,
                   **kwargs):
        """
        Filter the ``pub`` table; store the results to ``self.filtered_pubs``

        In the case of invalid filter(s), prints an error message

        The acceptable formats for received/accepted/published dates are:

            (1) YYYY
            (2) YYYY-MM
            (3) YYYY-MM-DD

        The results are ordered by the following in ascending order:

            (1) Publisher
            (2) Journal
            (3) Received date
            (4) Accepted date

        Parameters
        ----------
        get_titles : bool
            Whether to include titles of the filtered entries to the result;
                False by default
        get_publication_type : bool
            Include publication types of the filtered entries;
                False by default
        get_no_of_author : bool
            Include number of authors the filtered entries to the result;
                False by default
        get_affiliations : bool
            Include affiliations of the filtered entries to the result;
                False by default

        Keyword Arguments
        -----------------
        normalized_publisher : list of str
            Normalized publisher name(s)
        normalized_journal : list of str
            Normalized journal name(s)
        min_received : str
            Earliest date of publication reception
        max_received : str
            Latest date of publication reception
        min_accepted : str
            Earliest date of publication acceptance
        max_accepted : str
            Latest date of publication acceptance
        min_published : str
            Earliest date of publication
        max_published : str
            Latest date of publication
        publication_types : str
            List of str; note that publication types are experimental

        Raises
        ------
        ValueError
            In the case of invalid filters

        """

        self.filtered_pubs = self._pub.filter_pjt(
                get_title=get_title,
                get_publication_type=get_publication_type,
                get_no_of_authors=get_no_of_authors,
                get_affiliations=get_affiliations,
                **kwargs)
