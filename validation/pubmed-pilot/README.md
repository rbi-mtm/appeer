# PubMed validation pilot

This is a deliberately small benchmark of 50 articles. Articles are selected
because PubMed supplies exact received, accepted, and electronic-publication
dates. It measures `appeer` agreement conditional on that metadata being
available; it does not estimate date availability in ordinary journal
populations.

The workflow has five commands:

```sh
python -m validation.scripts.pubmed_pilot discover
python -m validation.scripts.pubmed_pilot freeze
python -m validation.scripts.pubmed_pilot harvest
python -m validation.scripts.pubmed_pilot run
python -m validation.scripts.pubmed_pilot compare
```

`sample.csv` and `sample-manifest.json` freeze the DOI list. `pubmed.xml` and
`reference.csv` preserve the reference metadata. `appeer.csv` records the
unchanged parser output. `comparisons.csv`, `summary.csv`, and `report.md`
contain the comparison results. `disagreements.csv` contains only unequal
date pairs; unavailable `appeer` dates are reported separately as missing.

For `published`, the reference is the earliest exact PubMed event labelled
`aheadofprint`, `epublish`, or `ArticleDate` with `DateType="Electronic"`.
Print, issue, indexing, and collection dates are ignored.
