"""Harvest free structured date observations without using appeer parsers."""

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from validation.scripts.common import (
    StudyClient,
    VALIDATION_ROOT,
    canonical_doi,
    crossref_date,
    iso_date,
    load_json,
    read_csv,
    write_csv,
)


OBSERVATION_FIELDS = [
    'doi', 'target_field', 'source', 'source_lineage', 'status',
    'raw_label', 'raw_value', 'normalized_date', 'semantic_concept',
    'source_field', 'source_record_id', 'source_url', 'retrieved_at',
    'response_sha256', 'explicit_or_inferred', 'precision', 'raw_path', 'notes',
]


def observation(doi, target, source, lineage, status, **values):
    row = {field: '' for field in OBSERVATION_FIELDS}
    row.update({
        'doi': doi,
        'target_field': target,
        'source': source,
        'source_lineage': lineage,
        'status': status,
    })
    row.update(values)
    return row


def provenance_values(provenance):
    return {key: provenance.get(key, '') for key in (
        'source_record_id', 'source_url', 'retrieved_at', 'response_sha256',
        'raw_path')}


def harvest_crossref(client, doi):
    source = 'crossref'
    lineage = 'crossref_publisher_deposit'
    response = client.get(f'https://api.crossref.org/works/{doi}')
    provenance = client.snapshot(response, source, doi)
    message = response.json()['message']
    mappings = {
        'received': [],
        'accepted': [('accepted', 'accepted')],
        'published': [
            ('published-online', 'published_online'),
            ('published', 'general_published'),
            ('published-print', 'print'),
        ],
    }
    rows = []
    for target, candidates in mappings.items():
        found = False
        for field, concept in candidates:
            if field not in message:
                continue
            raw, precision = crossref_date(message[field])
            if raw is None:
                continue
            found = True
            if concept in {'general_published', 'print'}:
                status = 'semantic_noncomparable'
            elif precision == 'day':
                status = 'observed'
            else:
                status = 'partial_precision'
            rows.append(observation(
                doi, target, source, lineage, status,
                raw_label=field,
                raw_value=json.dumps(message[field], sort_keys=True),
                normalized_date=raw if precision == 'day' else '',
                semantic_concept=concept,
                source_field=f'message.{field}',
                explicit_or_inferred=(
                    'inferred' if concept == 'general_published' else 'explicit'),
                precision=precision,
                **provenance_values(provenance),
            ))
        if not found:
            rows.append(observation(
                doi, target, source, lineage, 'source_field_missing',
                **provenance_values(provenance)))
    return rows


def local_name(element):
    return element.tag.rsplit('}', 1)[-1].lower()


def xml_date(element):
    direct = element.attrib.get('iso-8601-date')
    normalized = iso_date(direct)
    if normalized:
        return normalized, 'day'
    parts = {}
    for child in element:
        name = local_name(child)
        if name in {'year', 'month', 'day'} and child.text:
            parts[name] = child.text.strip()
    try:
        if {'year', 'month', 'day'} <= parts.keys():
            import datetime as dt
            return dt.date(int(parts['year']), int(parts['month']),
                           int(parts['day'])).isoformat(), 'day'
        if {'year', 'month'} <= parts.keys():
            return f"{int(parts['year']):04d}-{int(parts['month']):02d}", 'month'
        if 'year' in parts:
            return f"{int(parts['year']):04d}", 'year'
    except ValueError:
        pass
    return None, 'unknown'


def parse_pubmed_xml(content, doi, provenance):
    root = ET.fromstring(content)
    source = 'pubmed'
    lineage = 'pubmed_publisher_deposit'
    mappings = {
        'received': ('received', 'received'),
        'accepted': ('accepted', 'accepted'),
        'aheadofprint': ('published', 'ahead_of_print'),
        'epublish': ('published', 'published_online'),
    }
    rows = []
    found = {'received': False, 'accepted': False, 'published': False}
    for element in root.iter():
        if local_name(element) != 'pubmedpubdate':
            continue
        status = element.attrib.get('PubStatus', '').lower()
        if status not in mappings:
            continue
        target, concept = mappings[status]
        value, precision = xml_date(element)
        if value is None:
            continue
        found[target] = True
        rows.append(observation(
            doi, target, source, lineage,
            'observed' if precision == 'day' else 'partial_precision',
            raw_label=status,
            raw_value=value,
            normalized_date=value if precision == 'day' else '',
            semantic_concept=concept,
            source_field=f'PubMedPubDate[@PubStatus="{status}"]',
            explicit_or_inferred='explicit', precision=precision,
            **provenance_values(provenance),
        ))
    for target, present in found.items():
        if not present:
            rows.append(observation(
                doi, target, source, lineage, 'source_field_missing',
                **provenance_values(provenance)))
    return rows


def harvest_pubmed(client, doi):
    search = client.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
        params={'db': 'pubmed', 'term': f'{doi}[aid]', 'retmode': 'json'})
    search_provenance = client.snapshot(search, 'pubmed-search', doi)
    identifiers = search.json().get('esearchresult', {}).get('idlist', [])
    if not identifiers:
        return [observation(
            doi, target, 'pubmed', 'pubmed_publisher_deposit',
            'source_not_covered', **provenance_values(search_provenance))
            for target in ('received', 'accepted', 'published')]
    pmid = identifiers[0]
    response = client.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
        params={'db': 'pubmed', 'id': pmid, 'retmode': 'xml'})
    provenance = client.snapshot(response, 'pubmed', pmid)
    return parse_pubmed_xml(response.content, doi, provenance)


def parse_jats_xml(content, doi, provenance):
    root = ET.fromstring(content)
    source = 'pmc_jats'
    lineage = 'pmc_publisher_or_author_deposit'
    rows = []
    found = {'received': False, 'accepted': False, 'published': False}
    for element in root.iter():
        name = local_name(element)
        date_type = element.attrib.get('date-type', '').lower()
        pub_type = element.attrib.get('pub-type', '').lower()
        publication_format = element.attrib.get(
            'publication-format', '').lower()
        target = concept = None
        status = 'observed'
        if name == 'date' and date_type in {'received', 'submitted'}:
            target, concept = 'received', date_type
        elif name == 'date' and date_type == 'accepted':
            target, concept = 'accepted', 'accepted'
        elif name == 'date' and date_type in {
                'accepted-manuscript', 'ahead-of-print'}:
            target, concept = 'published', date_type.replace('-', '_')
        elif name == 'pub-date' and (date_type in {'collection', 'issue'}
                                     or pub_type in {'ecollection'}):
            target, concept = 'published', 'collection'
            status = 'semantic_noncomparable'
        elif name == 'pub-date' and (pub_type == 'ppub'
                                     or publication_format == 'print'):
            target, concept = 'published', 'print'
            status = 'semantic_noncomparable'
        elif name == 'pub-date' and (pub_type == 'epub'
                                     or (publication_format == 'electronic'
                                         and date_type in {
                                             '', 'pub', 'online',
                                             'original-publication'})
                                     or date_type in {
                                         'online', 'original-publication'}):
            target, concept = 'published', 'published_online'
        if target is None:
            continue
        value, precision = xml_date(element)
        if value is None:
            continue
        found[target] = True
        if status == 'observed' and precision != 'day':
            status = 'partial_precision'
        rows.append(observation(
            doi, target, source, lineage, status,
            raw_label=date_type or pub_type,
            raw_value=value,
            normalized_date=value if precision == 'day' else '',
            semantic_concept=concept,
            source_field=f'{name}[@date-type="{date_type}"]',
            explicit_or_inferred='explicit', precision=precision,
            **provenance_values(provenance),
        ))
    for target, present in found.items():
        if not present:
            rows.append(observation(
                doi, target, source, lineage, 'source_field_missing',
                **provenance_values(provenance)))
    return rows


def harvest_europe_pmc(client, doi):
    response = client.get(
        'https://www.ebi.ac.uk/europepmc/webservices/rest/search',
        params={'query': f'DOI:{doi}', 'format': 'json',
                'resultType': 'core', 'pageSize': 5})
    provenance = client.snapshot(response, 'europe-pmc', doi)
    results = response.json().get('resultList', {}).get('result', [])
    match = next((item for item in results
                  if canonical_doi(item.get('doi')) == doi), None)
    if match is None:
        return ([observation(
            doi, target, 'europe_pmc', 'europe_pmc_aggregated_record',
            'source_not_covered', **provenance_values(provenance))
                 for target in ('received', 'accepted', 'published')], None)

    rows = []
    for target in ('received', 'accepted'):
        rows.append(observation(
            doi, target, 'europe_pmc', 'europe_pmc_aggregated_record',
            'source_field_missing', **provenance_values(provenance)))
    published = match.get('electronicPublicationDate')
    if published:
        precision = 'day' if len(published) == 10 else 'partial'
        rows.append(observation(
            doi, 'published', 'europe_pmc',
            'europe_pmc_aggregated_record',
            'observed' if precision == 'day' else 'partial_precision',
            raw_label='electronicPublicationDate', raw_value=published,
            normalized_date=published if len(published) == 10 else '',
            semantic_concept='published_online',
            source_field='result.electronicPublicationDate',
            explicit_or_inferred='explicit',
            precision=precision,
            **provenance_values(provenance),
        ))
    else:
        rows.append(observation(
            doi, 'published', 'europe_pmc',
            'europe_pmc_aggregated_record', 'source_field_missing',
            **provenance_values(provenance)))
    return rows, match.get('pmcid')


def harvest_pmc_jats(client, doi, pmcid):
    if not pmcid:
        return [observation(
            doi, target, 'pmc_jats', 'pmc_publisher_or_author_deposit',
            'source_not_covered') for target in (
                'received', 'accepted', 'published')]
    response = client.get(
        f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML')
    provenance = client.snapshot(response, 'pmc-jats', pmcid)
    return parse_jats_xml(response.content, doi, provenance)


def inaccessible_rows(doi, source, lineage, error):
    return [observation(
        doi, target, source, lineage, 'source_inaccessible', notes=str(error))
        for target in ('received', 'accepted', 'published')]


def harvest(args):
    study = load_json(args.study)
    client = StudyClient(
        study['user_agent'], study['request_timeout_seconds'],
        study['minimum_request_interval_seconds'])
    sample = read_csv(args.sample)
    if args.limit:
        sample = sample[:args.limit]
    rows = []
    completed = set()
    if args.output.exists() and not args.refresh:
        rows = read_csv(args.output)
        sources = {}
        for row in rows:
            sources.setdefault(row['doi'], set()).add(row['source'])
        required_sources = {'crossref', 'pubmed', 'europe_pmc', 'pmc_jats'}
        completed = {doi for doi, found in sources.items()
                     if required_sources <= found}
    processed = 0
    for index, article in enumerate(sample, 1):
        doi = canonical_doi(article['doi'])
        if doi is None:
            raise ValueError(f"Malformed DOI in sample: {article['doi']!r}")
        if doi in completed:
            continue
        print(f'[{index}/{len(sample)}] {doi}', flush=True)
        try:
            rows.extend(harvest_crossref(client, doi))
        except (requests.RequestException, ValueError, KeyError) as error:
            rows.extend(inaccessible_rows(
                doi, 'crossref', 'crossref_publisher_deposit', error))
        try:
            rows.extend(harvest_pubmed(client, doi))
        except (requests.RequestException, ValueError, ET.ParseError) as error:
            rows.extend(inaccessible_rows(
                doi, 'pubmed', 'pubmed_publisher_deposit', error))
        pmcid = None
        try:
            europe_rows, pmcid = harvest_europe_pmc(client, doi)
            rows.extend(europe_rows)
        except (requests.RequestException, ValueError, KeyError) as error:
            rows.extend(inaccessible_rows(
                doi, 'europe_pmc', 'europe_pmc_aggregated_record', error))
        try:
            rows.extend(harvest_pmc_jats(client, doi, pmcid))
        except (requests.RequestException, ValueError, ET.ParseError) as error:
            rows.extend(inaccessible_rows(
                doi, 'pmc_jats',
                'pmc_publisher_or_author_deposit', error))
        processed += 1
        if processed % args.checkpoint_every == 0:
            write_csv(args.output, OBSERVATION_FIELDS, rows)
    if processed:
        write_csv(args.output, OBSERVATION_FIELDS, rows)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        '--study', type=Path,
        default=VALIDATION_ROOT / 'config' / 'study.json')
    result.add_argument(
        '--sample', type=Path,
        default=VALIDATION_ROOT / 'sampling' / 'candidate-sample.csv')
    result.add_argument(
        '--output', type=Path,
        default=VALIDATION_ROOT / 'references' / 'observations.csv')
    result.add_argument('--limit', type=int)
    result.add_argument('--refresh', action='store_true')
    result.add_argument('--checkpoint-every', type=int, default=10)
    return result


def main():
    args = parser().parse_args()
    if args.checkpoint_every < 1:
        raise SystemExit('--checkpoint-every must be positive')
    harvest(args)


if __name__ == '__main__':
    main()
