"""Bounded, rate-limit-aware HTTP retrieval."""

import datetime
from email.utils import parsedate_to_datetime
import time

import click
import requests

from appeer import __version__
from appeer.general import log as _log
from appeer.general.config import Config
from appeer.scrape import scrape_reports as reports


DEFAULT_USER_AGENT = (
    f'appeer/{__version__} (scientific metadata client; '
    'contact: juraj.ovcar@gmail.com)'
)


class Request:
    """Send one bounded request sequence and retain its final outcome."""

    def __init__(self, url, _queue=None, session=None, sleeper=None,
                 user_agent=None):
        self._queue = _queue
        self._session = session or requests
        self._sleep = sleeper or time.sleep
        self.user_agent = user_agent
        self.url = url
        self.success = False
        self.status = None
        self.error = None
        self.response = None

    def send(self, head=False, **kwargs):
        settings = Config().settings or {}
        defaults = settings.get('ScrapeDefaults', {})
        max_tries = int(kwargs.get('max_tries', defaults.get('max_tries', 3)))
        retry_sleep = float(kwargs.get(
            'retry_sleep_time', defaults.get('retry_sleep_time', 10)))
        timeout = float(kwargs.get('timeout', defaults.get('timeout', 30)))
        fallback_429 = float(kwargs.get(
            'rate_limit_sleep_time', defaults.get('429_sleep_time', 5)))
        validate_article = kwargs.get('validate_article', not head)
        user_agent = (kwargs.get('user_agent') or self.user_agent
                      or defaults.get('user_agent') or DEFAULT_USER_AGENT)

        if max_tries < 1:
            raise ValueError('max_tries must be at least one.')

        headers = {'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml'}
        for attempt in range(max_tries):
            self._rprint(_log.underlined_message(
                f'HTTPS Request {attempt + 1}/{max_tries}'))
            try:
                method = self._session.head if head else self._session.get
                self.response = method(
                    self.url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,
                )
                self.status = self.response.status_code

                if self.status == 429:
                    self.error = 'Too many requests'
                    self._rprint(reports.requests_report(self))
                    if attempt < max_tries - 1:
                        self._sleep(self._retry_after_seconds(
                            self.response, fallback_429))
                    continue

                if not 200 <= self.status < 300:
                    self.error = f'HTTP {self.status}'
                elif validate_article and not self._is_article_response(self.response):
                    self.error = 'Response is not a supported article page'
                else:
                    self.success = True
                    self.error = None

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as exc:
                self.status = None
                self.error = type(exc).__name__

            self._rprint(reports.requests_report(self))
            if self.success:
                return
            if attempt < max_tries - 1:
                self._sleep(retry_sleep)

        self.success = False
        self._rprint('Scraping failed.\n')

    @staticmethod
    def _is_article_response(response):
        content_type = response.headers.get('Content-Type', '').casefold()
        text = response.text or ''
        if content_type and 'html' not in content_type:
            return False
        has_doi = 'citation_doi' in text.casefold()
        has_supported_publisher = (
            'royal society of chemistry' in text.casefold()
            or 'nature publishing group' in text.casefold()
            or 'springer nature' in text.casefold()
        )
        return has_doi and has_supported_publisher

    @staticmethod
    def _retry_after_seconds(response, fallback):
        value = response.headers.get('Retry-After')
        if not value:
            return fallback
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=datetime.UTC)
                return max(0.0, (
                    retry_at - datetime.datetime.now(datetime.UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return fallback

    def _rprint(self, message):
        if self._queue:
            self._queue.put(message)
        else:
            click.echo(message)
