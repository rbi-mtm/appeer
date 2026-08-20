# Frozen confirmatory sample

The confirmatory sample was frozen on 2026-08-20 before reference harvesting.
It contains exactly 1,250 unique DOIs: 250 per publisher, 50 per journal, and
10 per journal-year. The deterministic split contains 500 development and 750
holdout records.

`frame-manifest.csv` records the count, path, and SHA-256 digest of each of the
125 complete Crossref ISSN/year frames. Those content-addressed frames contain
471,188 unique DOI records and are retained locally under `frames/`; they are
generated API data and are not committed to Git. `sample-manifest.json` binds
the exact sample to the protocol, roster, frame manifest, seed, and sample hash.

Frames use Crossref `journal-article` records whose publication date falls in
2021–2025. The frame is not filtered for external reference coverage, access,
article-history completeness, or later eligibility classification.
