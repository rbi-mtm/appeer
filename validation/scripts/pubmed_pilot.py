"""Run the simple 50-article PubMed benchmark pilot."""

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import requests

from appeer import __version__
from appeer.parse.parsers.preparser import Preparser
from appeer.scrape.request import Request
from validation.scripts.common import (
    StudyClient, VALIDATION_ROOT, canonical_doi, load_json, read_csv,
    sha256_bytes, write_csv)


PILOT_ROOT = VALIDATION_ROOT / 'pubmed-pilot'
SEED = 'appeer-pubmed-pilot-v1'
PUBLISHER_ORDER = ('NAT', 'RSC', 'ACS', 'APS', 'ELS')
USER_AGENT = 'appeer-pubmed-pilot/1.0 (mailto:juraj.ovcar@gmail.com)'
EXCLUDED_PUBLICATION_TYPES = {
    'Biography', 'Comment', 'Editorial', 'Guideline', 'Historical Article',
    'Letter', 'News', 'Practice Guideline', 'Preprint', 'Published Erratum',
    'Retraction of Publication', 'Retracted Publication', 'Review',
}
EXCLUDED_TITLE = re.compile(
    r'^(author correction|publisher correction|correction|corrigendum|erratum|'
    r'retraction|editorial|comment|reply)\b', re.IGNORECASE)

CANDIDATE_FIELDS = [
    'doi', 'pmid', 'pii', 'publisher', 'journal', 'issn', 'title',
    'publication_types', 'received', 'accepted', 'published',
    'received_source', 'accepted_source', 'published_source', 'selection_rank',
]
SAMPLE_FIELDS = [
    'doi', 'pmid', 'publisher', 'journal', 'issn', 'title', 'selection_rank',
]
REFERENCE_FIELDS = [
    'doi', 'pmid', 'pii', 'publisher', 'journal', 'received', 'accepted',
    'published', 'received_source', 'accepted_source', 'published_source',
    'source_url', 'retrieved_at', 'raw_sha256',
]
APPEER_FIELDS = [
    'doi', 'publisher', 'journal', 'source_url', 'transport_success',
    'http_status', 'transport_error', 'parser', 'parser_success', 'received',
    'accepted', 'published', 'input_sha256', 'package_version', 'git_revision',
    'parsed_at', 'warnings',
]
COMPARISON_FIELDS = [
    'doi', 'publisher', 'journal', 'target_field', 'pubmed_date', 'appeer_date',
    'status', 'source_url', 'transport_error',
]
SUMMARY_FIELDS = [
    'publisher', 'target_field', 'reference_articles', 'n_compared',
    'exact_matches', 'mismatches', 'missing_values',
    'percent_exact_agreement',
]


def text(element):
    if element is None:
        return ''
    return ' '.join(''.join(element.itertext()).split())


def xml_date(element):
    if element is None:
        return None
    parts = {}
    for name in ('Year', 'Month', 'Day'):
        child = element.find(name)
        if child is not None and child.text:
            parts[name.lower()] = child.text.strip()
    if set(parts) != {'year', 'month', 'day'}:
        return None
    month = parts['month']
    if not month.isdigit():
        months = {
            name: number for number, name in enumerate(
                ('', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug',
                 'sep', 'oct', 'nov', 'dec'))
        }
        month = months.get(month[:3].lower())
    try:
        return dt.date(
            int(parts['year']), int(month), int(parts['day'])).isoformat()
    except (TypeError, ValueError):
        return None


def first_date(events, labels):
    matching = sorted((value, label) for label, value in events
                      if label in labels and value)
    if not matching:
        return '', ''
    earliest = matching[0][0]
    sources = sorted({label for value, label in matching if value == earliest})
    return earliest, '|'.join(sources)


def parse_pubmed_xml(content, journal_lookup=None):
    root = ET.fromstring(content)
    records = []
    for article in root.findall('.//PubmedArticle'):
        citation = article.find('MedlineCitation')
        pubmed_data = article.find('PubmedData')
        pmid = text(citation.find('PMID'))
        identifiers = {}
        for identifier in pubmed_data.findall('./ArticleIdList/ArticleId'):
            identifiers[identifier.attrib.get('IdType', '').lower()] = text(
                identifier)
        doi = canonical_doi(identifiers.get('doi'))
        if not doi:
            for location in citation.findall('./Article/ELocationID'):
                if location.attrib.get('EIdType', '').lower() == 'doi':
                    doi = canonical_doi(text(location))
                    if doi:
                        break
        if not doi:
            continue

        events = []
        for event in pubmed_data.findall('./History/PubMedPubDate'):
            label = event.attrib.get('PubStatus', '').lower()
            value = xml_date(event)
            if value:
                events.append((label, value))
        for event in citation.findall('./Article/ArticleDate'):
            if event.attrib.get('DateType', '').lower() == 'electronic':
                value = xml_date(event)
                if value:
                    events.append(('article_date_electronic', value))

        received, received_source = first_date(events, {'received'})
        accepted, accepted_source = first_date(events, {'accepted'})
        published, published_source = first_date(events, {
            'aheadofprint', 'epublish', 'article_date_electronic'})
        publication_types = sorted({
            text(item) for item in citation.findall(
                './Article/PublicationTypeList/PublicationType') if text(item)})
        journal = journal_lookup or {}
        record = {
            'doi': doi,
            'pmid': pmid,
            'pii': identifiers.get('pii', ''),
            'publisher': journal.get('publisher', ''),
            'journal': journal.get('journal', ''),
            'issn': journal.get('issn', ''),
            'title': text(citation.find('./Article/ArticleTitle')),
            'publication_types': '|'.join(publication_types),
            'received': received,
            'accepted': accepted,
            'published': published,
            'received_source': received_source,
            'accepted_source': accepted_source,
            'published_source': published_source,
        }
        records.append(record)
    return records


def candidate_is_eligible(record):
    types = set(record['publication_types'].split('|'))
    if 'Journal Article' not in types or types & EXCLUDED_PUBLICATION_TYPES:
        return False
    if EXCLUDED_TITLE.match(record['title']):
        return False
    dates = [record[field] for field in ('received', 'accepted', 'published')]
    return all(dates) and dates == sorted(dates)


def save_content(directory, content, suffix):
    digest = sha256_bytes(content)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{digest}{suffix}'
    if not path.exists():
        path.write_bytes(content)
    return path, digest


def discover(args):
    journals = load_json(args.journals)
    client = StudyClient(USER_AGENT, timeout=30, minimum_interval=0.34)
    candidates = []
    manifest = []
    seen = set()
    for index, journal in enumerate(journals, 1):
        query = (
            f'"{journal["issn"]}"[Journal] AND '
            f'("{args.start_year}/01/01"[Date - Publication] : '
            f'"{args.end_year}/12/31"[Date - Publication])')
        search = client.get(
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            params={'db': 'pubmed', 'term': query, 'retmode': 'json',
                    'retmax': args.candidates_per_journal, 'sort': 'pub date'})
        search_data = search.json()['esearchresult']
        pmids = search_data.get('idlist', [])
        eligible_count = 0
        raw_sha = ''
        if pmids:
            response = client.get(
                'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
                params={'db': 'pubmed', 'id': ','.join(pmids),
                        'retmode': 'xml'})
            raw_path, raw_sha = save_content(
                PILOT_ROOT / 'discovery-raw', response.content, '.xml')
            for record in parse_pubmed_xml(response.content, journal):
                if record['doi'] in seen or not candidate_is_eligible(record):
                    continue
                seen.add(record['doi'])
                material = '\x1f'.join((
                    SEED, record['publisher'], record['pmid'], record['doi']))
                record['selection_rank'] = hashlib.sha256(
                    material.encode('utf-8')).hexdigest()
                candidates.append(record)
                eligible_count += 1
        manifest.append({
            'publisher': journal['publisher'], 'journal': journal['journal'],
            'issn': journal['issn'], 'query': query,
            'pubmed_count': search_data.get('count', '0'),
            'pmids_retrieved': len(pmids), 'eligible_candidates': eligible_count,
            'raw_sha256': raw_sha,
        })
        print(f'[{index}/{len(journals)}] {journal["journal"]}: '
              f'{eligible_count} usable', flush=True)
    candidates.sort(key=lambda row: row['selection_rank'])
    write_csv(PILOT_ROOT / 'candidates.csv', CANDIDATE_FIELDS, candidates)
    write_csv(PILOT_ROOT / 'discovery-manifest.csv', [
        'publisher', 'journal', 'issn', 'query', 'pubmed_count',
        'pmids_retrieved', 'eligible_candidates', 'raw_sha256'], manifest)


def freeze(args):
    candidates = read_csv(args.candidates)
    by_publisher = defaultdict(list)
    for row in candidates:
        by_publisher[row['publisher']].append(row)
    selected = []
    selected_dois = set()
    for publisher in PUBLISHER_ORDER:
        rows = sorted(by_publisher[publisher],
                      key=lambda row: row['selection_rank'])
        for row in rows[:min(args.preferred_per_publisher, len(rows))]:
            selected.append(row)
            selected_dois.add(row['doi'])
    remaining = sorted(
        (row for row in candidates if row['doi'] not in selected_dois),
        key=lambda row: row['selection_rank'])
    selected.extend(remaining[:args.size - len(selected)])
    if len(selected) != args.size:
        raise ValueError(
            f'Only {len(selected)} eligible PubMed candidates; need {args.size}')
    selected.sort(key=lambda row: (
        PUBLISHER_ORDER.index(row['publisher']), row['journal'],
        row['selection_rank']))
    sample = [{field: row[field] for field in SAMPLE_FIELDS}
              for row in selected]
    if len({row['doi'] for row in sample}) != args.size:
        raise ValueError('Frozen pilot DOI list is not unique')
    write_csv(args.output, SAMPLE_FIELDS, sample)
    manifest = {
        'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'seed': SEED,
        'article_count': len(sample),
        'publisher_counts': dict(sorted(Counter(
            row['publisher'] for row in sample).items())),
        'sample_sha256': sha256_bytes(args.output.read_bytes()),
        'candidate_sha256': sha256_bytes(args.candidates.read_bytes()),
        'selection': (
            'Up to 10 lowest deterministic ranks per publisher, then lowest '
            'remaining ranks across publishers until 50.'),
    }
    path = args.output.with_name('sample-manifest.json')
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')


def harvest(args):
    sample = read_csv(args.sample)
    pmids = [row['pmid'] for row in sample]
    client = StudyClient(USER_AGENT, timeout=30, minimum_interval=0.34)
    response = client.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
        params={'db': 'pubmed', 'id': ','.join(pmids), 'retmode': 'xml'})
    raw_path = PILOT_ROOT / 'pubmed.xml'
    raw_path.write_bytes(response.content)
    digest = sha256_bytes(response.content)
    parsed = {row['doi']: row for row in parse_pubmed_xml(response.content)}
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    references = []
    for article in sample:
        record = parsed.get(article['doi'])
        if not record or not candidate_is_eligible({
                **record, 'publication_types': record['publication_types']}):
            raise ValueError(
                f'Frozen PubMed record lost required metadata: {article["doi"]}')
        references.append({
            **record,
            'publisher': article['publisher'],
            'journal': article['journal'],
            'source_url': response.url,
            'retrieved_at': timestamp,
            'raw_sha256': digest,
        })
    write_csv(args.output, REFERENCE_FIELDS, references)


def publisher_url(article, reference):
    doi = article['doi']
    suffix = doi.split('/', 1)[1]
    publisher = article['publisher']
    if publisher == 'NAT':
        return f'https://www.nature.com/articles/{suffix}'
    if publisher == 'RSC':
        codes = {
            'Chemical Science': 'sc', 'RSC Advances': 'ra',
            'Organic & Biomolecular Chemistry': 'ob',
            'Journal of Materials Chemistry A': 'ta',
            'Environmental Science: Processes & Impacts': 'em',
        }
        return (f"https://pubs.rsc.org/en/content/articlehtml/"
                f"{reference['published'][:4]}/{codes[article['journal']]}/"
                f'{suffix}')
    if publisher == 'ACS':
        return f'https://pubs.acs.org/doi/{doi}'
    if publisher == 'APS':
        codes = {
            'Physical Review Letters': 'prl', 'Physical Review A': 'pra',
            'Physical Review B': 'prb', 'Physical Review D': 'prd',
            'Physical Review X': 'prx',
        }
        return (f"https://journals.aps.org/{codes[article['journal']]}/"
                f'abstract/{doi}')
    if reference.get('pii'):
        return ('https://www.sciencedirect.com/science/article/pii/'
                f"{reference['pii']}")
    return f'https://doi.org/{doi}'


class NullQueue:
    def put(self, value):
        del value


def git_revision():
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', 'HEAD'], check=True,
            capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ''
    return result.stdout.strip()


def run_appeer(args):
    sample = read_csv(args.sample)
    references = {row['doi']: row for row in read_csv(args.references)}
    session = requests.Session()
    results = []
    revision = git_revision()
    for index, article in enumerate(sample, 1):
        if index > 1:
            time.sleep(args.delay)
        url = publisher_url(article, references[article['doi']])
        request = Request(
            url, session=session, sleeper=time.sleep, user_agent=USER_AGENT,
            _queue=NullQueue())
        request.send(max_tries=1, timeout=30)
        digest = ''
        parser_name = ''
        parser_success = False
        dates = {'received': '', 'accepted': '', 'published': ''}
        warnings = []
        parsed_at = dt.datetime.now(dt.timezone.utc).isoformat()
        if request.response is not None and request.response.content:
            raw_path, digest = save_content(
                PILOT_ROOT / 'html', request.response.content, '.html')
            if request.success:
                parser_class, loaded = Preparser(str(raw_path)).determine_parser()
                if parser_class:
                    parser = parser_class(loaded)
                    parser_name = parser.__class__.__name__
                    parser_success = parser.success and parser.doi == article['doi']
                    dates = {
                        field: getattr(parser, f'normalized_{field}') or ''
                        for field in ('received', 'accepted', 'published')}
                    warnings = list(parser.warnings)
                    if parser.doi != article['doi']:
                        warnings.append('doi_article_mismatch')
                    parsed_at = parser.provenance['parsed_at']
        results.append({
            'doi': article['doi'], 'publisher': article['publisher'],
            'journal': article['journal'], 'source_url': url,
            'transport_success': str(request.success).lower(),
            'http_status': request.status or '',
            'transport_error': request.error or '', 'parser': parser_name,
            'parser_success': str(parser_success).lower(), **dates,
            'input_sha256': digest, 'package_version': __version__,
            'git_revision': revision, 'parsed_at': parsed_at,
            'warnings': json.dumps(sorted(set(warnings))),
        })
        write_csv(args.output, APPEER_FIELDS, results)
        print(f'[{index}/{len(sample)}] {article["doi"]}: '
              f'{request.status or request.error}', flush=True)


def compare(args):
    sample = read_csv(args.sample)
    references = {row['doi']: row for row in read_csv(args.references)}
    appeer = {row['doi']: row for row in read_csv(args.appeer)}
    comparisons = []
    for article in sample:
        for target in ('received', 'accepted', 'published'):
            expected = references[article['doi']][target]
            actual = appeer[article['doi']][target]
            status = 'missing' if not actual else (
                'exact' if actual == expected else 'mismatch')
            comparisons.append({
                'doi': article['doi'], 'publisher': article['publisher'],
                'journal': article['journal'], 'target_field': target,
                'pubmed_date': expected, 'appeer_date': actual,
                'status': status,
                'source_url': appeer[article['doi']]['source_url'],
                'transport_error': appeer[article['doi']]['transport_error'],
            })
    write_csv(args.comparisons, COMPARISON_FIELDS, comparisons)
    write_csv(args.disagreements, COMPARISON_FIELDS, [
        row for row in comparisons if row['status'] == 'mismatch'])

    summary = []
    for publisher in ('OVERALL', *PUBLISHER_ORDER):
        scoped = comparisons if publisher == 'OVERALL' else [
            row for row in comparisons if row['publisher'] == publisher]
        for target in ('received', 'accepted', 'published'):
            rows = [
                row for row in scoped if row['target_field'] == target]
            counts = Counter(row['status'] for row in rows)
            compared = counts['exact'] + counts['mismatch']
            summary.append({
                'publisher': publisher, 'target_field': target,
                'reference_articles': len(rows), 'n_compared': compared,
                'exact_matches': counts['exact'],
                'mismatches': counts['mismatch'],
                'missing_values': counts['missing'],
                'percent_exact_agreement': (
                    f'{100 * counts["exact"] / compared:.1f}'
                    if compared else ''),
            })
    write_csv(args.summary, SUMMARY_FIELDS, summary)

    sample_counts = Counter(row['publisher'] for row in sample)
    retrieved_counts = Counter(
        row['publisher'] for row in appeer.values()
        if row['transport_success'] == 'true')
    report = [
        '# PubMed pilot result',
        '',
        'The frozen sample contains 50 articles for which PubMed supplied '
        'received, accepted, and electronic-publication dates. This is a '
        'benchmark conditional on complete PubMed metadata, not a test of '
        'metadata coverage in ordinary journal populations.',
        '',
        '## Sample and retrieval',
        '',
        '| Publisher | Articles | Publisher pages retrieved |',
        '|---|---:|---:|',
    ]
    for publisher in PUBLISHER_ORDER:
        report.append(
            f'| {publisher} | {sample_counts[publisher]} | '
            f'{retrieved_counts[publisher]} |')
    report.extend([
        f'| **Overall** | **{len(sample)}** | '
        f'**{sum(retrieved_counts.values())}** |',
        '',
        'APS contributes no articles because the searched APS journals did '
        'not expose complete PubMed lifecycle triplets in the discovery '
        'records.',
        '',
        '## Exact comparison',
        '',
        '| Publisher | Date | N compared | Exact | Mismatch | Missing | Exact agreement |',
        '|---|---|---:|---:|---:|---:|---:|',
    ])
    for row in summary:
        agreement = (f'{row["percent_exact_agreement"]}%'
                     if row['percent_exact_agreement'] else 'not estimable')
        report.append(
            f'| {row["publisher"]} | {row["target_field"]} | '
            f'{row["n_compared"]} | {row["exact_matches"]} | '
            f'{row["mismatches"]} | {row["missing_values"]} | '
            f'{agreement} |')
    overall_compared = sum(
        int(row['n_compared']) for row in summary
        if row['publisher'] == 'OVERALL')
    report.extend(['', '## Conclusion', ''])
    if not overall_compared:
        report.extend([
            'No publisher article page was retrieved successfully in this '
            'environment, so `appeer` produced no dates. Accuracy is therefore '
            'not estimable from this run. These unavailable outputs are counted '
            'as missing, not as date disagreements; `disagreements.csv` contains '
            'only genuine unequal date pairs.',
            '',
            'Do not scale this exact procedure to 1,250 articles yet. First '
            'establish reliable publisher-page retrieval, then rerun this '
            'frozen pilot without changing the DOI list or parsers.',
        ])
    else:
        report.append(
            'Review the disagreement table and retrieval failures before '
            'deciding whether to scale this procedure.')
    args.report.write_text('\n'.join(report) + '\n', encoding='utf-8')


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(required=True)
    discover_parser = commands.add_parser('discover')
    discover_parser.add_argument(
        '--journals', type=Path,
        default=VALIDATION_ROOT / 'config' / 'journals.json')
    discover_parser.add_argument('--start-year', type=int, default=2021)
    discover_parser.add_argument('--end-year', type=int, default=2025)
    discover_parser.add_argument('--candidates-per-journal', type=int,
                                 default=200)
    discover_parser.set_defaults(action=discover)
    freeze_parser = commands.add_parser('freeze')
    freeze_parser.add_argument('--candidates', type=Path,
                               default=PILOT_ROOT / 'candidates.csv')
    freeze_parser.add_argument('--output', type=Path,
                               default=PILOT_ROOT / 'sample.csv')
    freeze_parser.add_argument('--size', type=int, default=50)
    freeze_parser.add_argument('--preferred-per-publisher', type=int, default=10)
    freeze_parser.set_defaults(action=freeze)
    harvest_parser = commands.add_parser('harvest')
    harvest_parser.add_argument('--sample', type=Path,
                                default=PILOT_ROOT / 'sample.csv')
    harvest_parser.add_argument('--output', type=Path,
                                default=PILOT_ROOT / 'reference.csv')
    harvest_parser.set_defaults(action=harvest)
    run_parser = commands.add_parser('run')
    run_parser.add_argument('--sample', type=Path,
                            default=PILOT_ROOT / 'sample.csv')
    run_parser.add_argument('--references', type=Path,
                            default=PILOT_ROOT / 'reference.csv')
    run_parser.add_argument('--output', type=Path,
                            default=PILOT_ROOT / 'appeer.csv')
    run_parser.add_argument('--delay', type=float, default=1)
    run_parser.set_defaults(action=run_appeer)
    compare_parser = commands.add_parser('compare')
    compare_parser.add_argument('--sample', type=Path,
                                default=PILOT_ROOT / 'sample.csv')
    compare_parser.add_argument('--references', type=Path,
                                default=PILOT_ROOT / 'reference.csv')
    compare_parser.add_argument('--appeer', type=Path,
                                default=PILOT_ROOT / 'appeer.csv')
    compare_parser.add_argument('--comparisons', type=Path,
                                default=PILOT_ROOT / 'comparisons.csv')
    compare_parser.add_argument('--disagreements', type=Path,
                                default=PILOT_ROOT / 'disagreements.csv')
    compare_parser.add_argument('--summary', type=Path,
                                default=PILOT_ROOT / 'summary.csv')
    compare_parser.add_argument('--report', type=Path,
                                default=PILOT_ROOT / 'report.md')
    compare_parser.set_defaults(action=compare)
    return root


def main():
    args = parser().parse_args()
    args.action(args)


if __name__ == '__main__':
    main()
