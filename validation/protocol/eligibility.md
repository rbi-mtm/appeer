# Confirmatory eligibility rules

These rules were frozen before sampling.

## Sampling-frame inclusion

A record enters a journal-year frame when Crossref returns it as a
`journal-article` for the configured ISSN with a publication date in 2021–2025
and it has a syntactically valid, unique DOI. Frame membership is independent of
reference metadata, OA status, appeer success, and publisher-page accessibility.

## Primary analytic eligibility

Include ordinary peer-reviewed original research, short research reports,
methods articles, registered reports with results, and systematic reviews or
meta-analyses that synthesize evidence using a declared method.

Exclude:

- corrections, errata, corrigenda, retractions, withdrawals, and expressions of
  concern;
- editorials, news, announcements, obituaries, meeting reports, book reviews,
  letters that do not report original research, comments, replies, and invited
  perspectives;
- narrative reviews, tutorials, roadmaps, and non-systematic surveys;
- protocols without results, data descriptors without research analysis, and
  peer-review reports;
- preprints, accepted manuscripts that never became journal articles, and
  duplicate or superseded DOI records.

Publisher article-type labels and the article itself take precedence over title
heuristics. When accessible evidence cannot resolve the type, classify the
record as `uncertain` and send it to manual adjudication. Classification must not
use appeer-extracted dates or the availability of reference dates.

The sample is never redrawn after eligibility screening. Exclusions remain in
the corpus and are reported by publisher, journal, year, and reason.
