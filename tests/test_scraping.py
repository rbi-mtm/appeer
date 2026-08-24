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
        self.closed = False

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

    def close(self):
        self.closed = True


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


@pytest.mark.parametrize(('url', 'publisher', 'doi'), [
    ('https://pubs.acs.org/doi/example',
     'American Chemical Society', '10.1021/example'),
    ('https://journals.aps.org/prl/abstract/example',
     'American Physical Society', '10.1103/example'),
    ('https://www.sciencedirect.com/science/article/pii/example',
     'Elsevier', '10.1016/example'),
])
def test_new_publisher_article_responses_require_matching_metadata(
        url, publisher, doi):
    article = (
        '<html><head>'
        f'<meta name="citation_publisher" content="{publisher}">'
        f'<meta name="citation_doi" content="{doi}">'
        '</head></html>'
    )
    request = Request(url, session=FakeSession([
        FakeResponse(text=article, url=url),
    ]))

    request.send(max_tries=1)

    assert request.success


def test_article_response_rejects_cross_publisher_doi_prefix():
    article = (
        '<html><head>'
        '<meta name="citation_publisher" content="American Chemical Society">'
        '<meta name="citation_doi" content="10.1103/example">'
        '</head></html>'
    )
    url = 'https://pubs.acs.org/doi/example'
    request = Request(url, session=FakeSession([
        FakeResponse(text=article, url=url),
    ]))

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Response is not a supported article page'


def test_redirect_to_unregistered_hostname_is_rejected_before_following():
    session = FakeSession([FakeResponse(302, headers={
        'Location': 'https://evil.example/article'})])
    request = Request('https://www.nature.com/articles/example', session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert len(session.calls) == 1


def test_nature_cookie_authorization_redirect_is_allowed(monkeypatch):
    session = FakeSession([
        FakeResponse(303, headers={
            'Location': (
                'https://idp.nature.com/authorize?redirect_uri='
                'https%3A%2F%2Fwww.nature.com%2Farticles%2Fexample')}),
        FakeResponse(302, headers={
            'Location': 'https://idp.nature.com/transit'}),
        FakeResponse(302, headers={
            'Location': 'https://www.nature.com/articles/example'}),
        FakeResponse(),
    ])
    monkeypatch.setattr(requests, 'Session', lambda: session)
    request = Request('https://www.nature.com/articles/example')

    request.send(max_tries=1)

    assert request.success
    assert len(session.calls) == 4
    assert session.closed


def test_nature_authorization_host_cannot_be_requested_directly():
    session = FakeSession([])
    request = Request('https://idp.nature.com/authorize', session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert session.calls == []


def test_nature_authorization_redirect_rejects_unexpected_path():
    session = FakeSession([FakeResponse(303, headers={
        'Location': 'https://idp.nature.com/unexpected'})])
    request = Request('https://www.nature.com/articles/example',
                      session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert len(session.calls) == 1


def test_nature_authorization_cannot_redirect_to_another_publisher():
    session = FakeSession([
        FakeResponse(303, headers={
            'Location': 'https://idp.nature.com/authorize'}),
        FakeResponse(302, headers={
            'Location': 'https://pubs.acs.org/doi/example'}),
    ])
    request = Request('https://www.nature.com/articles/example',
                      session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert len(session.calls) == 2


def test_elsevier_linking_hub_resolves_matching_pii():
    linking_url = (
        'https://linkinghub.elsevier.com/retrieve/pii/S1385894722062337')
    article_url = (
        'https://www.sciencedirect.com/science/article/pii/'
        'S1385894722062337')
    session = FakeSession([
        FakeResponse(302, headers={'Location': linking_url}),
        FakeResponse(url=linking_url),
        FakeResponse(text=(
            '<html><head>'
            '<meta name="citation_publisher" content="Elsevier">'
            '<meta name="citation_doi" '
            'content="10.1016/j.cej.2022.140753">'
            '</head></html>'), url=article_url),
    ])
    request = Request('https://doi.org/10.1016/j.cej.2022.140753',
                      session=session)

    request.send(max_tries=1)

    assert request.success
    assert request.response.url == article_url
    assert [call[1] for call in session.calls] == [
        'https://doi.org/10.1016/j.cej.2022.140753',
        linking_url,
        article_url,
    ]


def test_elsevier_linking_hub_cannot_be_requested_directly():
    session = FakeSession([])
    request = Request(
        'https://linkinghub.elsevier.com/retrieve/pii/S123',
        session=session)

    request.send(max_tries=1)

    assert not request.success
    assert request.error == 'Unsafe or unsupported request URL'
    assert session.calls == []


def test_elsevier_linking_hub_rejects_malformed_pii_path():
    session = FakeSession([FakeResponse(302, headers={
        'Location': 'https://linkinghub.elsevier.com/retrieve/pii/../S123'})])
    request = Request('https://doi.org/10.1016/example', session=session)

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
    ('https://pubs.acs.org/doi/10.1021/example', 'ACS'),
    ('https://journals.aps.org/prl/abstract/10.1103/example', 'APS'),
    ('https://www.sciencedirect.com/science/article/pii/example', 'ELS'),
    ('https://pubs.rsc.org/article', 'RSC'),
    ('https://www.nature.com/articles/example', 'NAT'),
    ('https://pubs.rsc.org.evil.example/article', 'Unknown'),
    ('https://www.sciencedirect.com.evil.example/article', 'Unknown'),
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
