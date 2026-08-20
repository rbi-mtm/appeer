# Validation protocol

## Research question

How accurately and reliably does `appeer` recover the true publication-history
dates of scholarly articles from the five publishers it currently supports?

The confirmatory analysis covers ACS, APS, Elsevier, Nature, and RSC. PLOS may
serve as a later positive control but is not substituted merely to increase the
publisher count.

## Target variables

`received` is the date on which the journal first received the initial
manuscript corresponding to the article. A source label of `submitted` is
harmonized to received only when the publisher defines it as initial receipt and
there is no contradictory transfer or resubmission evidence. The original label
is always retained.

`accepted` is the explicit editorial acceptance date following peer review. If
a publisher distinguishes editorial and production acceptance, both are kept
and the lifecycle date displayed on the article as Accepted is the target.

`published` is the earliest date on which the peer-reviewed paper became
publicly available from the publisher. It includes a public accepted manuscript,
ahead-of-print article, journal pre-proof, Published Online, Available online,
or First published event. It excludes preprints, private proofs, repository
deposit dates, PubMed/PMC indexing dates, issue assignment, later print dates,
and copyright years. Version of Record is used only when no earlier public
peer-reviewed publisher version is evidenced.

The downstream targets are `accepted - received` and `published - accepted`.
Negative or otherwise suspicious intervals remain inspectable but are excluded
from ordinary aggregates.

## Sampling

The first round uses the journals in `config/journals.json` and calendar years
2021 through 2025. A journal-year DOI frame is obtained from Crossref by ISSN,
reconciled against the publisher archive, canonicalized, and deduplicated.

Each of the 125 journal-year cells contributes ten articles:

- seven population-random records, selected without regard to reference-source
  availability;
- three reference-enriched peer-reviewed records with at least one explicit
  structured lifecycle reference.

Within each cell, three random and one enriched articles form the development
set; four random and two enriched articles form the locked holdout. Selection is
the lowest deterministic SHA-256 rank under the seed in `config/study.json`.
Frames, candidate reserves, exclusions, and hashes are retained. A sampled
article is not replaced merely because it is inaccessible or difficult.

The random cohort preserves corrections, editorials, letters, and other
nonstandard content so false inclusion and rejection can be measured. Original
peer-reviewed research is the primary accuracy population; reviews and methods
articles are secondary strata.

## Reference evidence

Reference observations are stored in long form, one row per DOI, target field,
source, and retrieval. PubMed, PMC, Europe PMC, Crossref, and publisher XML often
repeat metadata created by the same publisher. Each observation therefore has a
`source_lineage`; mirrors of the same deposit count as one lineage rather than
independent votes.

The free reference routes are:

- PubMed XML publication history;
- PMC and Europe PMC JATS/XML;
- Crossref accepted and published-online fields;
- freely accessible publisher pages, PDFs, JATS, or structured metadata;
- Springer Nature OA JATS, APS Harvest OA metadata, and Elsevier OA XML where
  available;
- OpenAlex only for sampling enrichment and identifier linkage.

Missingness in a source is not an `appeer` error. The controlled statuses are
defined in `source-semantics.yml`.

## Blinded adjudication

Reference observations and article eligibility are normalized before an
adjudicator can view `appeer` output. For discrepancies, evidence is inspected
in this order: labelled publisher history, publisher XML/JATS or structured
state, article PDF, PubMed/PMC XML, then Crossref.

Two adjudicators independently review every holdout discrepancy, every missing
`appeer` value, and a random 10% of apparent exact matches. A third adjudicator
resolves disagreements while blinded to the `appeer` value until recording an
independent decision.

Confidence levels are:

- A: an explicit date supported by two distinct retrieval lineages, or by a
  publisher artifact and a matching structured deposit;
- B: one explicit publisher artifact independently confirmed by two reviewers;
- C: a partial, inferred, or generic publication date;
- U: unresolved or unobservable.

Primary accuracy denominators include A and B only. C is used for sensitivity
analysis; U contributes to reference-availability reporting.

## Metrics

Report each date separately and preserve every denominator:

- A/B reference ascertainment in the random cohort;
- extraction coverage among eligible random articles;
- exact, one-day, two-to-seven-day, and greater-than-seven-day discrepancies;
- wrong-semantic, false-nonmissing, and missing-when-truth-exists rates;
- complete-triplet coverage and whole-record exact agreement;
- exact, signed, and absolute errors in both derived intervals;
- journal/publisher median, IQR, 10th, and 90th percentiles;
- micro-averages and equal-journal macro-averages.

Use Wilson intervals for binomial proportions and cluster bootstrap intervals
for journal- and publisher-level quantities. Never combine the enriched and
random cohorts into an unweighted headline value.

## Missingness and bias

Model complete-triplet availability by publisher, journal, year, article type,
OA status, discipline, author count, citation style, transport outcome, and
reference-source availability. Compare adjudicated intervals between complete
and incomplete records and repeat aggregates with inverse-probability weights.

An aggregate is selection-sensitive when adjustment changes its median by more
than three days or 10% of the adjudicated IQR. High conditional date accuracy
does not establish unbiased population estimates when completeness is selective.

## Locked evaluation

Freeze frames, DOI lists, cohort assignments, raw responses, and their hashes
before parser development. Only development labels are visible while parsers are
changed. Freeze the parser Git revision and analysis environment before opening
holdout evidence. Run the holdout once. A holdout-driven parser change requires
a newly sampled holdout and cannot replace the reported result.

## Validation thresholds

A publisher/date requires a target of 100 A/B holdout references and an absolute
minimum of 80, with at least 12 per journal; otherwise its status is
`insufficient_evidence`.

Date-accuracy validation requires:

- pooled silent-wrong rate no greater than 0.5%;
- publisher silent-wrong rate no greater than 1%, with a one-sided 95% upper
  confidence bound no greater than 3%;
- exact agreement of at least 98% pooled and 97% per publisher;
- exact-or-one-day agreement of at least 99%;
- no DOI/article mismatch, wrong semantic event, or undiagnosed impossible
  sequence entering an aggregate.

Operational validation additionally requires at least 90% coverage for each
date, 85% complete triplets, and no journal below 75% complete triplets in the
random original-research cohort. A parser can be `accurate_but_incomplete`.
Missing dates are preferable to silently wrong ones.
