# Structured-source implementation smoke

This is not a validation result. Its eight DOIs are existing parser fixtures and
therefore belong to development, not to the confirmatory sample.

On 2026-08-20 the independent harvester completed all four free structured
routes without an access failure and produced 107 source/field observations with
verified raw-response hashes:

- 17 explicit, day-precision target observations;
- 13 explicit but semantically noncomparable general, print, or collection
  dates;
- one partial-precision date;
- 22 fields missing from a source that covered the article;
- 54 source-not-covered observations.

The smoke illustrates the intended source complementarity. Crossref supplied
five exact online dates and two acceptance dates; PubMed supplied one received/
accepted pair; and PMC JATS supplied two complete lifecycle pairs plus two
electronic-publication dates. The non-biomedical Elsevier and RSC fixture
articles received no exact lifecycle triplet from these repositories, confirming
that publisher artifacts and manual adjudication are necessary.

`structured-source-observations.csv` is the normalized audit table. Its
`raw_path` and `response_sha256` values point to content-addressed responses under
`references/raw/`.
