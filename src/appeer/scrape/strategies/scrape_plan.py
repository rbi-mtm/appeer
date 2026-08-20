"""Create a scrape plan from a list of URLs"""

import sys
from urllib.parse import urlsplit

from functools import cached_property
from collections import Counter

import click

from appeer.scrape.scrape_reports import scrape_strategy_report

from appeer.scrape.strategies.mapping import JournalScrapeMap
from appeer.scrape.input_handling import\
        parse_data_source, handle_input_reading

class ScrapePlan:
    """
    Get scrape strategies from URL list

    """

    def __init__(self, url_list):
        """
        Get scrape strategies from URL list

        Parameters
        ----------
        url_list : list
            URL list of strings starting with https://

        """


        # Special case of one URL
        if isinstance (url_list, str):
            url_list = [url_list]

        if not all(isinstance(url, str) for url in url_list):
            raise ValueError('All URLs must be given as a string')

        self.url_list = url_list
        self._jsm = JournalScrapeMap()

    @cached_property
    def _domains(self):
        """
        Get the list of domains from the ``self.url_list``

        """

        domains = []

        for url in self.url_list:
            parsed = None
            try:
                parsed = urlsplit(url)
                hostname = parsed.hostname
                invalid_port = parsed.port not in (None, 443)
            except ValueError:
                hostname = None
                invalid_port = True

            if (parsed is None or parsed.scheme != 'https' or not hostname or invalid_port
                    or parsed.username is not None or parsed.password is not None):
                domains.append('invalid_url')
            elif hostname in self._jsm.strategy_map:
                domains.append(hostname)
            else:
                domains.append('unknown')

        return domains

    @cached_property
    def strategies(self):
        """
        Use JournalScrapeMap to get strategies from ``self._domains``

        Returns
        -------
        strats : dict
            Dictionary of form URL index: strategy_map[domain]

        """

        strats = {}

        for i, domain in enumerate(self._domains):
            strats[f'{i}'] = {'url': self.url_list[i]}
            strats[f'{i}'].update(self._jsm.get_strategy(domain))

        return strats

    @cached_property
    def journals_count(self):
        """
        Count how many different journals are found

        Returns
        -------
        count : Counter
            Counter of different journals

        """

        journals = [strategy['journal_code']
                for strategy in self.strategies.values()]

        count = Counter(journals)

        return count

    @cached_property
    def strategies_count(self):
        """
        Count how many different strategies are found

        Returns
        -------
        count : Counter
            Counter of different strategies

        """

        strategy_codes = [strategy['strategy_code']
                for strategy in self.strategies.values()]

        count = Counter(strategy_codes)

        return count

    @cached_property
    def strategy_report(self):
        """
        Create a strategy report for the inputted URL list

        Returns
        -------
        report : str
            Strategy report for the inputted URL list

        """

        report = scrape_strategy_report(plan=self, offset=0)

        return report

def preview_plan(publications):
    """
    Preview a scrape plan for ``publications`` (no scraping is done)

    ``publications`` can be a list of URLs or a string (path to a file)

    In the case a filepath is provided, the file can be either a JSON file
        (e.g. ``PoP.json`` file containing ``['article_url']`` keys)
        or a plaintext file with each URL written in a new line

    Parameters
    ----------
    publications : list | str
        A list of URLs or a path to a file

    """

    data_source,\
        data_source_type,\
        p_ex_message,\
        j_ex_message = parse_data_source(publications)

    reading_passed, reading_report = handle_input_reading(publications,
            data_source_type,
            str(p_ex_message),
            str(j_ex_message))

    click.echo(reading_report)

    if not reading_passed:
        sys.exit()

    plan = ScrapePlan(data_source)

    click.echo(plan.strategy_report)
