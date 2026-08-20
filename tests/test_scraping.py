"""Offline HTTP, URL, DOI, and archive hardening tests."""

import zipfile

import pytest
import requests

from appeer.general import utils
from appeer.scrape.request import DEFAULT_USER_AGENT, Request
from appeer.scrape.strategies.scrape_plan import ScrapePlan


ARTICLE_HTML = '''
<html><head>
<meta name="citation_doi" content="10.1038/example">
<meta name="citation_publisher" content="Nature Publishing Group">
</head></html>
'''


class FakeResponse:
    def __init__(self, status_code=200, text=ARTICLE_HTML, headers=None,
                 url='https://www.nature.com/articles/example'):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {'Content-Type': 'text/html'}
        self.url = url


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def get(self, url, **kwargs):
        return self._call('GET', url, kwargs)

    def head(self, url, **kwargs):
        return self._call('HEAD', url, kwargs)

    def _call(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_transparent_user_agent_redirect_and_timeout_are_configurable():
    session = FakeSession([
        FakeResponse(302, headers={
            'Location': 'https://www.nature.com/articles/redirected'}),
        FakeResponse(url='https://www.nature.com/articles/redirected'),
    ])
    request = Request('https://doi.org/10.1038/example', session=session)

    request.send(timeout=4)

    assert request.success
    assert request.response.url.endswith('/redirected')
    assert session.calls[0][2]['timeout'] == 4
    assert session.calls[0][2]['allow_redirects'] is False
    assert session.calls[0][2]['headers']['User-Agent'] == DEFAULT_USER_AGENT


def test_retry_after_is_honored_before_retry():
    sleeps = []
    session = FakeSession([
        FakeResponse(429, headers={'Retry-After': '7'}),
        FakeResponse(),
    ])
    request = Request('https://www.nature.com/articles/example',
                      session=session, sleeper=sleeps.append)

    request.send(max_tries=2, retry_sleep_time=99)

    assert request.success
    assert sleeps == [7.0]
    assert len(session.calls) == 2


def test_timeout_retry_exhaustion_is_bounded():
    sleeps = []
    session = FakeSession([
        requests.exceptions.Timeout(),
        requests.exceptions.Timeout(),
    ])
    request = Request('https://www.nature.com/articles/example',
                      session=session, sleeper=sleeps.append)

    request.send(max_tries=2, retry_sleep_time=3)

    assert not request.success
    assert request.error == 'Timeout'
    assert sleeps == [3]
    assert len(session.calls) == 2


def test_http_success_block_page_is_not_an_article():
    response = FakeResponse(text='<html><h1>Verify you are human</h1></html>')
    request = Request('https://www.nature.com/articles/example',
                      session=FakeSession([response]))

    request.send(max_tries=1)

    assert not request.success
    assert request.status == 200
    assert request.error == 'Response is not a supported article page'


def test_redirect_to_unregistered_hostname_is_rejected_before_following():
    session = FakeSession([FakeResponse(302, headers={
        'Location': 'https://evil.example/article'})])
    request = Request('https://www.nature.com/articles/example', session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert len(session.calls) == 1


def test_request_exception_is_reported_without_escaping():
    request = Request(
        'https://www.nature.com/articles/example',
        session=FakeSession([requests.exceptions.TooManyRedirects()]))

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'TooManyRedirects'


@pytest.mark.parametrize(('url', 'expected_journal'), [
    ('https://pubs.rsc.org/article', 'RSC'),
    ('https://www.nature.com/articles/example', 'NAT'),
    ('https://pubs.rsc.org.evil.example/article', 'Unknown'),
    ('https://pubs.rsc.org@evil.example/article', 'Invalid_URL'),
    ('https://pubs.rsc.org:444/article', 'Invalid_URL'),
    ('http://pubs.rsc.org/article', 'Invalid_URL'),
])
def test_strategy_uses_exact_parsed_hostname(url, expected_journal):
    assert ScrapePlan(url).strategies['0']['journal_code'] == expected_journal


@pytest.mark.parametrize(('value', 'valid'), [
    ('10.1038/s41598-025-92476-w', True),
    ('https://doi.org/10.1038/S41598-025-92476-W', True),
    ('10.1038 malformed', False),
    ('prefix 10.1038/example suffix', False),
    ('10.123/x', False),
])
def test_doi_handling_is_canonical_and_not_fuzzy(value, valid):
    assert utils.check_doi_format(value) is valid
    assert (utils.get_doi_substring(value) is not None) is valid


def test_archive_member_cannot_escape_target(tmp_path):
    archive = tmp_path / 'unsafe.zip'
    target = tmp_path / 'target'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('../escaped.txt', 'unsafe')

    with pytest.raises(ValueError, match='escapes target'):
        utils.extract_archive(str(archive), str(target))

    assert not (tmp_path / 'escaped.txt').exists()


def test_safe_archive_extracts_normally(tmp_path):
    archive = tmp_path / 'safe.zip'
    target = tmp_path / 'target'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('nested/article.html', ARTICLE_HTML)

    assert utils.extract_archive(str(archive), str(target))
    assert (target / 'nested' / 'article.html').read_text() == ARTICLE_HTML
