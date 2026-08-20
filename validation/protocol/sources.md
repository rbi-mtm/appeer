# Free reference-source assessment

This source assessment was reviewed on 2026-08-20. A source is considered
independent only when both its data origin and transmission lineage are distinct.
Most scholarly date services instead redistribute publisher-created metadata;
they are useful corroboration routes but not statistically independent votes.

## PubMed

PubMed XML supports optional, exact publication-history values for `received`,
`accepted`, `aheadofprint`, and `epublish`. Its required journal publication date
may instead be a later print or issue date. NLM defines received as receipt for
review and electronic/ahead-of-print dates as dates on which the article became
publicly available. [PubMed XML provider specification](https://www.ncbi.nlm.nih.gov/books/NBK3828/?report=reader)

E-utilities are free and support batch retrieval. The documented limit is three
requests per second without an API key and ten with a free key.
[NCBI E-utilities policy](https://www.ncbi.nlm.nih.gov/books/NBK25497/?report=reader)

Coverage is journal- and discipline-dependent, and history fields are optional.
Records are supplied by publishers, although NLM validates provider samples
against the published article. [PubMed data evaluation](https://www.ncbi.nlm.nih.gov/pubmed/help/tech-eval)

## PMC and JATS

JATS represents received and accepted events under `<history>` and electronic
publication separately under `<pub-date>`. [JATS history definition](https://jats.nlm.nih.gov/publishing/tag-library/1.0/n-4ax0.html)

PMC's OAI-PMH API provides JATS metadata for PMC records and reusable full text
for the open subset, at no more than three requests per second.
[PMC OAI-PMH API](https://pmc.ncbi.nlm.nih.gov/tools/oai/)

PMC is strongest for biomedical, OA, and funder-deposited articles. Its XML is a
publisher or author deposit and therefore shares lineage with publisher pages and
often PubMed.

## Europe PMC

Europe PMC provides free REST search and OA `fullTextXML`. Its
`electronicPublicationDate` can corroborate first online publication. Its
`firstPublicationDate` chooses the earlier electronic or print value and may
algorithmically complete partial dates, so it is not accepted as exact truth
without corroboration. [Europe PMC REST service](https://europepmc.org/RestfulWebService)

Europe PMC mirrors PubMed and PMC records. Agreement among those three interfaces
does not constitute three independent sources.

## Crossref

Crossref's public REST API exposes publisher-deposited metadata without sign-up.
[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
It supports accepted, published-online, published-print, and general publication
dates, but has no received field for journal articles.
[Crossref date filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)

Acceptance and full day-precision dates are optional. Generic `published` is
depositor-defined; `created`, `deposited`, and `indexed` are not publication
events. [Crossref date guidance](https://www.crossref.org/documentation/principles-practices/best-practices/bibliographic/)

## Publisher sources

- Springer Nature's free OA API supplies metadata and, where available, JATS for
  OA Nature content. Its free tier allows 500 requests per day.
  [OA API](https://dev.springernature.com/docs/api-endpoints/open-access/),
  [access limits](https://dev.springernature.com/subscription/)
- APS Harvest exposes OA article JSON without authentication and additional
  XML/PDF formats according to authorization. It is a publisher source, not an
  independent deposit. [APS Harvest](https://harvest.aps.org/docs/harvest-api)
- Elsevier Article Retrieval provides OA XML with an API key, while non-OA full
  content depends on entitlements. It is optional corroboration rather than a
  universal free reference. [Elsevier access rules](https://dev.elsevier.com/tecdoc_article_access.html)
- RSC offers journal XML for licensed text-and-data mining rather than an
  unrestricted public bulk API. Public article history and PDFs are therefore
  the free adjudication route. [RSC TDM information](https://www.rsc.org/journals-books-databases/research-tools/text-and-data-mining/)
- ACS public article-history labels and freely accessible PDFs are manually
  admissible. Automated universal ACS retrieval is not assumed.

Publisher artifacts are the closest documentary evidence to the article but
still share the underlying publisher origin. The study gains independence by
using separately written extractors, frozen bytes, blinded adjudication, and
multiple transmission lineages.

## PLOS and OpenAlex

PLOS exposes explicit `received_date`, `accepted_date`, and `publication_date`
through a free API. [PLOS fields](https://api.plos.org/solr/search-fields/),
[rate limits](https://api.plos.org/solr/faq) It is reserved as a future positive
control because appeer does not currently support PLOS.

OpenAlex has a general publication date but no received or accepted dates. It
aggregates sources such as Crossref and PubMed, so it is used only for DOI/PMID/
PMCID linkage, OA status, and sampling enrichment.
[OpenAlex work fields](https://developers.openalex.org/api-reference/works/get-a-single-work),
[free access](https://developers.openalex.org/api-reference/authentication)

## Repository-coverage pilot

`coverage-pilot.csv` compares Crossref journal-article counts with Europe PMC
records and Europe PMC full-text presence for 2021–2025. It characterizes
repository reach, not lifecycle-field completeness.

The pilot shows why a single biomedical reference source would bias the study:
Nature and RSC examples have extensive PMC coverage; ACS records are commonly
indexed but much less often have PMC full text; APS full text is negligible; and
Elsevier coverage changes sharply between neuroscience and non-biomedical
journals. Publisher artifacts and manual adjudication are therefore required for
APS, most Elsevier disciplines, and substantial portions of ACS.
