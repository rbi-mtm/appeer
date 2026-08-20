"""Run the frozen appeer revision on publisher HTML without changing parsers."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urljoin, urlsplit

import requests

from appeer import __version__
from appeer.parse.parsers.preparser import Preparser
from validation.scripts.common import (
    VALIDATION_ROOT, canonical_doi, read_csv, write_csv)


RESULT_FIELDS = [
    'doi', 'parser', 'package_version', 'git_revision', 'input_sha256',
    'parsed_at', 'success', 'received', 'accepted', 'published', 'warnings',
]

RETRIEVAL_FIELDS = [
    'doi', 'publisher', 'requested_url', 'final_url', 'http_status', 'outcome',
    'error', 'retrieved_at', 'input_sha256', 'raw_path',
]

EXPECTED_HOSTS = {
    'NAT': {'www.nature.com'},
    'RSC': {'pubs.rsc.org'},
    'ACS': {'pubs.acs.org'},
    'APS': {'journals.aps.org'},
    'ELS': {'www.sciencedirect.com'},
}

TRANSIENT_HOSTS = {
    'doi.org', 'dx.doi.org', 'link.aps.org', 'linkinghub.elsevier.com',
    'xlink.rsc.org',
}


class PublisherRateLimiter:
    """Keep one request clock across every article for one publisher."""

    def __init__(self, interval, clock=time.monotonic, sleeper=time.sleep):
        self.interval = interval
        self.clock = clock
        self.sleeper = sleeper
        self.last_request = None

    def wait(self):
        if self.last_request is None:
            return
        remaining = self.interval - (self.clock() - self.last_request)
        if remaining > 0:
            self.sleeper(remaining)

    def mark(self):
        self.last_request = self.clock()


def git_revision():
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', 'HEAD'], check=True,
            capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ''
    return result.stdout.strip()


def allowed_url(url, publisher, final=False):
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    allowed = EXPECTED_HOSTS[publisher]
    if not final:
        allowed = allowed | TRANSIENT_HOSTS
    return (parsed.scheme == 'https' and parsed.hostname in allowed
            and parsed.port in (None, 443) and parsed.username is None
            and parsed.password is None)


def retry_delay(response, fallback):
    value = response.headers.get('Retry-After')
    try:
        return max(float(value), 0) if value else fallback
    except ValueError:
        return fallback


def publisher_url(article):
    doi = canonical_doi(article['doi'])
    publisher = article['publisher']
    suffix = doi.split('/', 1)[1]
    if publisher == 'NAT':
        return f'https://www.nature.com/articles/{suffix}'
    if publisher == 'RSC':
        codes = {
            'Chemical Science': 'sc',
            'RSC Advances': 'ra',
            'Organic & Biomolecular Chemistry': 'ob',
            'Journal of Materials Chemistry A': 'ta',
            'Environmental Science: Processes & Impacts': 'em',
        }
        code = codes[article['journal']]
        return (f"https://pubs.rsc.org/en/content/articlehtml/{article['year']}/"
                f'{code}/{suffix}')
    if publisher == 'ACS':
        return f'https://pubs.acs.org/doi/{doi}'
    if publisher == 'APS':
        codes = {
            'Physical Review Letters': 'prl',
            'Physical Review A': 'pra',
            'Physical Review B': 'prb',
            'Physical Review D': 'prd',
            'Physical Review X': 'prx',
        }
        return (f"https://journals.aps.org/{codes[article['journal']]}/abstract/"
                f'{doi}')
    return f'https://doi.org/{doi}'


def retrieve(session, requested, publisher, timeout, user_agent,
             minimum_interval, limiter=None):
    current = requested
    limiter = limiter or PublisherRateLimiter(minimum_interval)
    response = None
    for redirect in range(8):
        if not allowed_url(current, publisher):
            raise ValueError(f'unsupported redirect host: {urlsplit(current).hostname}')
        limiter.wait()
        response = session.get(
            current, headers={
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml',
            }, timeout=timeout, allow_redirects=False)
        limiter.mark()
        if response.status_code == 429:
            time.sleep(retry_delay(response, 10))
            continue
        if response.status_code in {500, 502, 503, 504}:
            time.sleep(2)
            continue
        if 300 <= response.status_code < 400:
            location = response.headers.get('Location')
            if not location:
                return response, current
            current = urljoin(current, location)
            continue
        if (publisher == 'ELS' and response.status_code == 200
                and urlsplit(current).hostname == 'linkinghub.elsevier.com'):
            match = re.fullmatch(r'/retrieve/pii/([A-Z0-9]+)',
                                 urlsplit(current).path, re.IGNORECASE)
            if not match:
                raise ValueError('Elsevier linking hub did not expose a safe PII')
            current = (
                'https://www.sciencedirect.com/science/article/pii/'
                f'{match.group(1)}')
            continue
        return response, current
    raise requests.TooManyRedirects('redirect or retry limit exhausted')


def empty_result(doi, revision, parsed_at, digest=None, warning=''):
    if digest is None:
        digest = hashlib.sha256(b'').hexdigest()
    return {
        'doi': doi, 'parser': 'unassigned', 'package_version': __version__,
        'git_revision': revision, 'input_sha256': digest,
        'parsed_at': parsed_at, 'success': 'false', 'received': '',
        'accepted': '', 'published': '', 'warnings': warning,
    }


def parse_file(path, expected_doi, revision):
    parsed_at = dt.datetime.now(dt.timezone.utc).isoformat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        parser_class, loaded = Preparser(str(path)).determine_parser()
        if parser_class is None:
            return empty_result(
                expected_doi, revision, parsed_at, digest, 'parser_unassigned')
        parser = parser_class(loaded)
        warnings = list(parser.warnings)
        parsed_doi = canonical_doi(parser.doi)
        if parsed_doi != expected_doi:
            warnings.append('doi_article_mismatch')
        success = parser.success and parsed_doi == expected_doi
        return {
            'doi': expected_doi,
            'parser': parser.__class__.__name__,
            'package_version': __version__,
            'git_revision': revision,
            'input_sha256': digest,
            'parsed_at': parser.provenance['parsed_at'],
            'success': str(success).lower(),
            'received': parser.normalized_received or '',
            'accepted': parser.normalized_accepted or '',
            'published': parser.normalized_published or '',
            'warnings': json.dumps(sorted(set(warnings))),
        }
    except (OSError, TypeError, ValueError, AttributeError) as error:
        return empty_result(
            expected_doi, revision, parsed_at, digest,
            f'parse_exception:{type(error).__name__}')


def process_publisher(publisher, articles, args, revision):
    session = requests.Session()
    limiter = PublisherRateLimiter(args.minimum_interval)
    result_checkpoint = args.checkpoints / f'{publisher}-results.csv'
    retrieval_checkpoint = args.checkpoints / f'{publisher}-retrievals.csv'
    refresh = publisher in args.refresh_publisher
    existing_results = (read_csv(result_checkpoint)
                        if result_checkpoint.exists() and not refresh else [])
    existing_retrievals = (read_csv(retrieval_checkpoint)
                           if retrieval_checkpoint.exists() and not refresh
                           else [])
    completed = {row['doi'] for row in existing_results}
    outputs = list(zip(existing_results, existing_retrievals))
    processed = 0
    for article in articles:
        doi = canonical_doi(article['doi'])
        if doi in completed:
            continue
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        requested = publisher_url(article)
        try:
            response, final_url = retrieve(
                session, requested, publisher, args.timeout, args.user_agent,
                args.minimum_interval, limiter)
            content = response.content
            digest = hashlib.sha256(content).hexdigest()
            raw_path = args.raw / publisher / f'{digest}.html'
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            if not raw_path.exists():
                raw_path.write_bytes(content)
            outcome = 'retrieved' if (
                200 <= response.status_code < 300
                and allowed_url(final_url, publisher, final=True)) else 'failed'
            error = '' if outcome == 'retrieved' else (
                f'HTTP {response.status_code}' if not 200 <= response.status_code < 300
                else 'unexpected final host')
            retrieval = {
                'doi': doi, 'publisher': publisher,
                'requested_url': requested, 'final_url': final_url,
                'http_status': response.status_code, 'outcome': outcome,
                'error': error, 'retrieved_at': timestamp,
                'input_sha256': digest,
                'raw_path': str(raw_path.relative_to(VALIDATION_ROOT)),
            }
            result = (parse_file(raw_path, doi, revision) if outcome == 'retrieved'
                      else empty_result(doi, revision, timestamp, digest, error))
        except (requests.RequestException, ValueError) as error:
            retrieval = {
                'doi': doi, 'publisher': publisher,
                'requested_url': requested, 'final_url': '', 'http_status': '',
                'outcome': 'failed', 'error': str(error),
                'retrieved_at': timestamp, 'input_sha256': '', 'raw_path': '',
            }
            result = empty_result(
                doi, revision, timestamp,
                warning=f'transport_exception:{type(error).__name__}')
        outputs.append((result, retrieval))
        processed += 1
        print(f'[{publisher} {len(outputs)}/{len(articles)}] {doi}', flush=True)
        if processed % 10 == 0:
            write_csv(result_checkpoint, RESULT_FIELDS,
                      [item[0] for item in outputs])
            write_csv(retrieval_checkpoint, RETRIEVAL_FIELDS,
                      [item[1] for item in outputs])
    if processed:
        write_csv(result_checkpoint, RESULT_FIELDS,
                  [item[0] for item in outputs])
        write_csv(retrieval_checkpoint, RETRIEVAL_FIELDS,
                  [item[1] for item in outputs])
    return outputs


def run(args):
    sample = read_csv(args.sample)
    by_publisher = defaultdict(list)
    for article in sample:
        by_publisher[article['publisher']].append(article)
    revision = args.parser_revision or git_revision()
    results = []
    retrievals = []
    with ThreadPoolExecutor(max_workers=len(by_publisher)) as executor:
        futures = {
            executor.submit(process_publisher, publisher, articles, args,
                            revision): publisher
            for publisher, articles in by_publisher.items()
        }
        for future in as_completed(futures):
            for result, retrieval in future.result():
                results.append(result)
                retrievals.append(retrieval)
            write_csv(args.output, RESULT_FIELDS, results)
            write_csv(args.retrievals, RETRIEVAL_FIELDS, retrievals)
    order = {row['doi']: index for index, row in enumerate(sample)}
    results.sort(key=lambda row: order[row['doi']])
    retrievals.sort(key=lambda row: order[row['doi']])
    write_csv(args.output, RESULT_FIELDS, results)
    write_csv(args.retrievals, RETRIEVAL_FIELDS, retrievals)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--sample', type=Path,
                        default=VALIDATION_ROOT / 'sampling' / 'sample.csv')
    result.add_argument('--output', type=Path,
                        default=VALIDATION_ROOT / 'runs' / 'appeer-results.csv')
    result.add_argument('--retrievals', type=Path,
                        default=VALIDATION_ROOT / 'runs' / 'retrievals.csv')
    result.add_argument('--raw', type=Path,
                        default=VALIDATION_ROOT / 'runs' / 'raw')
    result.add_argument('--checkpoints', type=Path,
                        default=VALIDATION_ROOT / 'runs' / 'checkpoints')
    result.add_argument('--timeout', type=float, default=30)
    result.add_argument('--minimum-interval', type=float, default=1)
    result.add_argument('--user-agent', default=(
        'appeer-validation/0.1 (scientific metadata validation; '
        'mailto:juraj.ovcar@gmail.com)'))
    result.add_argument('--refresh-publisher', action='append', default=[],
                        choices=sorted(EXPECTED_HOSTS))
    result.add_argument('--parser-revision', default='',
                        help='Frozen parser Git revision recorded in results')
    return result


def main():
    run(parser().parse_args())


if __name__ == '__main__':
    main()
