"""Offline tests for the small PubMed validation pilot."""

import argparse
import csv
from pathlib import Path

from validation.scripts.common import write_csv
from validation.scripts.pubmed_pilot import (
    CANDIDATE_FIELDS, candidate_is_eligible, freeze, parse_pubmed_xml,
    publisher_url)


PUBMED_XML = b'''<PubmedArticleSet><PubmedArticle>
  <MedlineCitation><PMID>123</PMID><Article>
    <ArticleTitle>Ordinary research article</ArticleTitle>
    <ELocationID EIdType="doi">10.1000/Example</ELocationID>
    <ArticleDate DateType="Electronic"><Year>2025</Year><Month>3</Month><Day>5</Day></ArticleDate>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
  </Article></MedlineCitation>
  <PubmedData>
    <History>
      <PubMedPubDate PubStatus="received"><Year>2024</Year><Month>Jan</Month><Day>2</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="accepted"><Year>2025</Year><Month>2</Month><Day>3</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="epublish"><Year>2025</Year><Month>3</Month><Day>8</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="aheadofprint"><Year>2025</Year><Month>3</Month><Day>6</Day></PubMedPubDate>
      <PubMedPubDate PubStatus="ppublish"><Year>2025</Year><Month>6</Month><Day>1</Day></PubMedPubDate>
    </History>
    <ArticleIdList>
      <ArticleId IdType="doi">10.1000/Example</ArticleId>
      <ArticleId IdType="pii">S123</ArticleId>
    </ArticleIdList>
  </PubmedData>
</PubmedArticle></PubmedArticleSet>'''


def test_pubmed_pilot_uses_earliest_electronic_date():
    record = parse_pubmed_xml(PUBMED_XML, {
        'publisher': 'ELS', 'journal': 'Example', 'issn': '0000-0000'})[0]

    assert record['doi'] == '10.1000/example'
    assert record['received'] == '2024-01-02'
    assert record['accepted'] == '2025-02-03'
    assert record['published'] == '2025-03-05'
    assert record['published_source'] == 'article_date_electronic'
    assert candidate_is_eligible(record)


def test_review_is_not_an_eligible_pilot_candidate():
    record = parse_pubmed_xml(PUBMED_XML)[0]
    record['publication_types'] = 'Journal Article|Review'

    assert not candidate_is_eligible(record)


def test_freeze_fills_short_publisher_strata_deterministically(tmp_path):
    rows = []
    for publisher, count in (('NAT', 2), ('RSC', 1), ('ACS', 3)):
        for index in range(count):
            row = {field: '' for field in CANDIDATE_FIELDS}
            row.update({
                'doi': f'10.1000/{publisher.lower()}-{index}',
                'pmid': f'{publisher}-{index}', 'publisher': publisher,
                'journal': f'{publisher} Journal', 'issn': '0000-0000',
                'title': 'Research', 'selection_rank': f'{index:064d}',
            })
            rows.append(row)
    candidates = tmp_path / 'candidates.csv'
    output = tmp_path / 'sample.csv'
    write_csv(candidates, CANDIDATE_FIELDS, rows)

    freeze(argparse.Namespace(
        candidates=candidates, output=output, size=5,
        preferred_per_publisher=1))

    with output.open(encoding='utf-8', newline='') as stream:
        sample = list(csv.DictReader(stream))
    assert len(sample) == 5
    assert len({row['doi'] for row in sample}) == 5


def test_sciencedirect_url_uses_pubmed_pii():
    assert publisher_url({
        'doi': '10.1016/j.example.2025.1', 'publisher': 'ELS',
        'journal': 'Example',
    }, {'pii': 'S123'}) == (
        'https://www.sciencedirect.com/science/article/pii/S123')
