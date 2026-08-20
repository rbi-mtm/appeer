# Validating publication-history dates

This directory contains the preregistered design and reproducible inputs for
measuring how accurately and completely `appeer` recovers received, accepted,
and first-publication dates.

The study has two cohorts. Population-random articles measure ordinary coverage
and selection bias. Reference-enriched articles efficiently measure accuracy
when strong comparison metadata exist. Results from the two cohorts must never
be pooled without the weighting specified in the protocol.

The intended first round covers 25 journals, five publication years, and 1,250
articles. It is split before inspection into 500 development and 750 locked
holdout articles.

## Workflow

1. Read and freeze [`protocol/protocol.md`](protocol/protocol.md) and the
   [reference-source assessment](protocol/sources.md).
2. Build Crossref DOI frames and deterministic candidate lists:

   ```sh
   python -m validation.scripts.sample fetch
   python -m validation.scripts.sample select
   ```

   Reconcile every Crossref frame against the publisher archive in
   `sampling/frame-reconciliation.csv`; explained differences remain in the
   audit trail.

3. Harvest free structured reference observations:

   ```sh
   python -m validation.scripts.harvest
   ```

   Override `APPEER_VALIDATION_USER_AGENT` if a different study contact should
   receive automated-access questions.

4. Finalize the enriched sample after lifecycle evidence has been harvested:

   ```sh
   python -m validation.scripts.sample finalize
   ```

5. Complete blinded adjudication using the templates in `adjudication/`.
6. Export an `appeer` run using `runs/appeer-results.csv` as the field contract.
7. Verify the frozen inputs and produce the locked report:

   ```sh
   python -m validation.scripts.verify --stage final
   python -m validation.scripts.analyze
   ```

Network operations are never part of the default test suite. Raw files are
content-addressed and accompanied by SHA-256 manifests. Do not commit or
redistribute copyrighted publisher HTML or PDFs without a compatible license.

`pilot/structured-source-smoke.csv` contains the eight verified parser-fixture
DOIs and exists only to test the independent reference harvesters. Because these
articles were already used in parser development, they must never enter reported
validation accuracy.
