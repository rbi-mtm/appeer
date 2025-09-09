"""Filter, plot, analyze results from pub.db"""

import appeer.general.utils as _utils
import appeer.general.log as _log

from appeer.db.pub_db import PubDB

from appeer.pub.analyzer import PubAnalyzer

class PubReSearcher:
    """
    Filter, plot, analyze results from pub.db

    """

    def __init__(self, filtered_pubs=None):
        """
        Connects to the pub.db database

        Parameters
        ----------
        filtered_pubs : None | list of appeer.db.tables.pub.FilteredPub
            Publications found through searching the ``pub.db`` database;
                normally they are found using ``self.search_pub``,
                but for now leave this parameter,
                so the results can be read from a (JSON) file

        """

        self._pub = PubDB(read_only=True).pub

        if filtered_pubs is None:
            filtered_pubs = []

        else:
            _utils.check_FilteredPub_type(filtered_pubs)

        self.filtered_pubs = filtered_pubs
        self._search_performed = bool(self.filtered_pubs)

        self.analyzer = PubAnalyzer(filtered_pubs=self.filtered_pubs)


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

        self._search_performed = True
        self.analyzer.load_data(filtered_pubs=self.filtered_pubs)


    @property
    def search_summary(self):
        """
        A short summary of the contents of the ``self.filtered_pubs`` attribute

        Returns
        -------
        report : str
            A short summary of the contents of ``self.filtered_pubs``

        """

        if not self._search_performed:
            report = 'No searches were yet performed. To perform a search, use the PubReSearcher().search_pub() method.'

        else:

            if self.filtered_pubs:

                align = len(max([
                    'no_of_publications',
                    'no_of_publishers',
                    'no_of_journals',
                    'min_received',
                    'max_received',
                    'min_accepted',
                    'max_accepted',
                    'min_published',
                    'max_published',
                    'average_ra',
                    'average_rp',
                    'average_ap'], key=len)) + 2

                b = self.analyzer.basic_search_results

                report = '\nSearch Summary\n'
                report += len('Search Summary') * '–' + '\n'

                report += f'{"no_of_publications":<{align}} {b["no_of_pubs"]}' + '\n'
                report += f'{"no_of_publishers":<{align}} {b["no_of_publishers"]}' + '\n'
                report += f'{"no_of_journals":<{align}} {b["no_of_journals"]}' + '\n'
                report += f'{"min_received":<{align}} {b["min_received"]}' + '\n'
                report += f'{"max_received":<{align}} {b["max_received"]}' + '\n'
                report += f'{"min_accepted":<{align}} {b["min_accepted"]}' + '\n'
                report += f'{"max_accepted":<{align}} {b["max_accepted"]}' + '\n'
                report += f'{"min_published":<{align}} {b["min_published"]}' + '\n'
                report += f'{"max_published":<{align}} {b["max_published"]}' + '\n'
                report += f'{"average_ra":<{align}} {b["average_ra"]:.2f}' + '\n'
                report += f'{"average_rp":<{align}} {b["average_rp"]:.2f}' + '\n'
                report += f'{"average_ap":<{align}} {b["average_ap"]:.2f}' + '\n\n'


                align = len(max(b['publishers'].keys(), key=len)) + 2

                report += 'Publishers (no. of publications)' + '\n'
                report += len('Publishers (no. of publications)') * '–' + '\n'

                for publisher, hits in b['publishers'].items():
                    report += f'{publisher:<{align}} ({hits})' + '\n'


                align = len(max(b['journals'].keys(), key=len)) + 2

                report += '\nJournals (no. of publications)' + '\n'
                report += len('Journals (no. of publications)') * '–' + '\n'

                for journal, hits in b['journals'].items():
                    report += f'{journal:<{align}} ({hits})' + '\n'

            else:
                report = 'No publications satisfy the inputted criteria.'

        return report
