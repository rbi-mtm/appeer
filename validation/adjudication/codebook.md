# Adjudication codebook

Adjudicators work from `manual-observations.csv` and immutable structured-source
observations. Holdout appeer output remains hidden until the independent labels
are recorded.

## Decision rules

1. Confirm the DOI, title, journal, and publisher before reading any date.
2. Record every visible label exactly; normalization is a separate field.
3. For received, choose initial journal receipt. Do not substitute revision,
   transfer, or resubmission without an explicit publisher definition.
4. For accepted, choose the displayed editorial acceptance lifecycle event.
5. For published, look for an earlier public peer-reviewed publisher version
   before accepting Version of Record, issue, or print dates.
6. Set `genuinely_absent` only after checking the labelled page, structured
   metadata, XML/JATS, and PDF routes that are freely available for that article.
7. Set `truth_unresolved` when comparable evidence conflicts or only a generic,
   partial, or inferred date remains.

## Evidence identifiers

An evidence ID has the form `SOURCE:SHA256:FIELD`, for example:

```text
PUBMED:12ab…ef90:PubMedPubDate[@PubStatus="accepted"]
```

Multiple IDs are separated by `|`. The rationale must explain semantic choices,
transfers, conflicts, accepted-manuscript publication, or unusual article types.

## Confidence

- A: explicit exact date with corroboration across distinct retrieval lineages.
- B: one explicit publisher artifact independently confirmed by two reviewers.
- C: inferred, generic, partial, or otherwise semantically weaker date.
- U: absent or unresolved.

Only A and B are used for primary exact-date accuracy.

## Severity

- `critical`: DOI mismatch, wrong article, wrong lifecycle concept, or an
  impossible sequence admitted without warning.
- `major`: returned date differs by more than one day or a template change causes
  systematic omission.
- `minor`: one-day difference, partial precision, or presentation-only issue.
- `upstream`: source conflict or malformed publisher metadata not caused by
  appeer.
