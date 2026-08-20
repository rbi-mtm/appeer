"""Scrape a single publication"""

import os

from appeer.general import utils as _utils

from appeer.jobs.action import Action
from appeer.scrape import scrape_reports as reports

from appeer.scrape.request import Request
from appeer.scrape.strategies.scrape_plan import ScrapePlan

class ScrapeAction(Action, action_type='scrape'): #pylint:disable=too-many-instance-attributes
    """
    Scrape a publication for later parsing

    Instances of the ScrapeAction class have dynamically created properties
        corresponding to the columns of the ``scrapes`` table in the
        ``jobs`` database

        Some of these properties are mutable; changing their value will
        update the value in the ``jobs`` database. The values of the
        non-mutable properties are set using ``self.new_action(**kwargs)``.
        The values of these properties may be edited only if
        ``self._action_mode == 'write'

    List of the dynamically generated properties:

    Dynamic Properties
    ------------------
    date : str
        Date and time of the job creation/run; mutable
    url : str
        URL that is being scraped
    journal : str
        Internal journal code of the URL
    strategy : str
        Internal scraping strategy code
    method : str
        Explicit name of the scraping method
    success : str
        Whether the action executed successfully; one of ('T', 'F'); mutable
    status : str
        Action status; one of ('I', 'W', 'R', 'E', 'X'); mutable
    out_file : str
        Path to the downloaded data; mutable
    parsed : str
        Whether the data corresponding to this action was parsed;
            one of ('T', 'F'); mutable

    """

    def __init__(self, label=None, action_index=None, action_mode='read'):
        """
        Connects to the job database and sets the action label and index

        Parameters
        ----------
        label : str
            Label of the job that the action corresponds to
        action_index : int
            Index of the action within the corresponding job

        """

        super().__init__(label=label,
                action_index=action_index,
                action_mode=action_mode)

        self.__download_directory = None

    def new_action(self,
            plan_entry,
            label=None,
            action_index=None):
        """ 
        Creates a new scrape action for a given plan entry

        Parameters
        ----------
        plan_entry : dict
            Dictionary containing ['url', 'journal_code', 'strategy_code']
        label : str
            Label of the job that the action corresponds to
        action_index : int
            Index of the action within the corresponding job

        """

        self._action_mode = 'write'

        if label:
            self.label = label

        if action_index:
            self.action_index = action_index

        self._initialize_action_common(url=plan_entry['url'],
                journal=plan_entry['journal_code'],
                strategy=plan_entry['strategy_code'],
                method=plan_entry['scraping_method'],
                status='W')

    def run(self, download_directory, _queue=None, **kwargs):
        """
        Run the scrape action

        If ``queue`` is given, messages will be sent to the ``queue``
            and logged in the job log file

        Parameters
        ----------
        download_directory : str
            Path to the directory into which to download files
        queue : queue.Queue
            If given, messages will be logged in the job log file

        Keyword Arguments
        -----------------
        max_tries : int
            Maximum number of tries to get a response from an URL before
                giving up
        retry_sleep_time : float
            Time (in seconds) to wait before trying a nonresponsive URL again

        """

        start_datetime = _utils.get_current_datetime()

        self._queue = _queue
        self.__download_directory = download_directory
        os.makedirs(self.__download_directory, exist_ok=True)

        self._action_mode = 'write'

        self.status = 'R'
        self.date = start_datetime

        self._aprint(reports.scrape_action_start(self))

        getattr(self, self.method)(**kwargs)

        self._aprint(reports.scrape_action_end(self))

        self.status = 'X'

    def _scrape_skip(self, **kwargs): #pylint:disable=unused-argument
        """
        Skip entry ('skip' strategy)

        """

        self._aprint('Skipping this entry.\n')
        self.success = 'F'

    def _scrape_html_simple(self, **kwargs):
        """
        Download HTML from an URL 

        Keyword Arguments
        -----------------
        max_tries : int
            Maximum number of tries to get a response from an URL before
                giving up
        retry_sleep_time : float
            Time (in seconds) to wait before trying a nonresponsive URL again
        _429_sleep_time : float
            Time (in minutes) to wait if received a 429 status code

        """

        kwargs.setdefault('url', self.url)

        request = Request(url=kwargs['url'], _queue=self._queue)

        del kwargs['url']

        request.send(**kwargs)

        if request.success:

            out_file = os.path.join(self.__download_directory,
                    f'{self.action_index}.html')

            _utils.write_text_to_file(filepath=out_file,
                    text_data=request.response.text)

            self.out_file = out_file
            self.success = 'T'

        else:
            self.success = 'F'

    def _doi_handler(self, **kwargs):
        """
        Resolve DOI and run the appropriate strategy

        Keyword Arguments
        -----------------
        max_tries : int
            Maximum number of tries to get a response from an URL before
                giving up
        retry_sleep_time : float
            Time (in seconds) to wait before trying a nonresponsive URL again
        _429_sleep_time : float
            Time (in minutes) to wait if received a 429 status code

        """

        request = Request(url=self.url, _queue=self._queue)
        request.send(head=True, validate_article=False, **kwargs)

        if request.success:

            resolved_url = request.response.url

            plan = ScrapePlan(url_list=resolved_url).strategies['0']

            self.journal = plan['journal_code']
            method = plan['scraping_method']

            _doi_report = {
                    'success': 'True',
                    'resolved_url': resolved_url,
                    'resolved_journal': self.journal,
                    'new_strategy': plan['strategy_code']
                    }

            self._aprint(reports.doi_report(_doi_report))

            kwargs['url'] = resolved_url
            getattr(self, method)(**kwargs)

        else:
            _doi_report = {
                    'success' : 'False',
                    'resolved_url': 'None',
                    'resolved_journal': 'None',
                    'new_strategy': 'None'
                    }

            self._aprint(reports.doi_report(_doi_report))

    def mark_as_parsed(self):
        """
        Marks the scrape action as parsed.

        If the action does not exist, does nothing.

        """

        if self._action_exists:

            self._action_mode = 'write'
            self.parsed = 'T'

    def mark_as_unparsed(self):
        """
        Marks the scrape action as unparsed.

        If the action does not exist, does nothing.

        """

        if self._action_exists:

            self._action_mode = 'write'
            self.parsed = 'F'
