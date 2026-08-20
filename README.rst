appeer
======

``appeer`` is experimental software for collecting publication metadata and
studying the length of peer review. It supports the current Royal Society of
Chemistry (RSC) and Nature Portfolio article layouts to the same standard.
Historical publisher layouts are intentionally unsupported.

Scientific behavior
-------------------

A parse is successful only when every canonical field is present and valid:
DOI, publisher, journal, title, publication type, authors, per-author
affiliations, received/accepted/published dates, and their normalized values.
DOIs and calendar dates are validated strictly. Author counts must agree with
the author and affiliation structures, and every author may have one or more
institutions.

Chronology anomalies remain inspectable warnings instead of universal parsing
failures. Suspicious or negative intervals are excluded from aggregate review
statistics by default. Failed parses retain independently extracted fields and
diagnostics in ``jobs.db`` but cannot be committed to ``pub.db``.

Each parse records the SHA-256 of its exact input bytes, parser identity,
package version, Git revision when available, parse timestamp, invalid fields,
and plausibility warnings. Successful publication rows carry the provenance
needed to trace them back to the parser and exact input.

Installation and verification
-----------------------------

Python 3.13 or newer is required.

.. code:: shell

   python -m pip install -e '.[test]'
   python -m compileall -q src
   pytest -q

The default suite is fully offline. Live publisher checks are opt-in and must
be explicitly requested:

.. code:: shell

   pytest -q --runslow

Build a wheel without adding another build frontend:

.. code:: shell

   python -m pip wheel --no-deps --wheel-dir dist .

Initialization
--------------

.. code:: shell

   appeer init

Commands that need configuration or databases report this instruction when
initialization has not yet been completed. Tests isolate configuration and data
through temporary XDG directories and never use a developer's real state.

Scraping and parsing
--------------------

Article HTML can be retrieved from URLs or canonical DOIs stored one per line,
or from a Publish or Perish JSON export:

.. code:: shell

   appeer scrape publications.txt
   appeer scrape publications.json

Only exact HTTPS hostnames registered for RSC, Nature, and DOI resolution are
accepted. Requests use a transparent configurable user agent, bounded retries
and timeouts, and ``Retry-After`` delays. HTTP success alone is not treated as a
valid article response.

Use ``appeer sjob --help``, ``appeer pjob --help``, and ``appeer cjob --help``
for the resumable scrape, parse, and commit workflows.

Publication search
------------------

Filters accept ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``. Minimum values mean
the beginning of a period and maximum values mean its inclusive end.

.. code:: shell

   appeer pub search --min_received 2024 --max_received 2025-06
   appeer pub search --get_title --get_author_names --get_affiliations \
       --output publications.json

JSON output is a list of publication objects. Optional fields are ``null``
unless their corresponding ``--get_*`` flag is passed. Warnings are always
included so excluded chronology intervals remain auditable.

Offline fixtures
----------------

Current-layout fixtures live in ``tests/fixtures``. ``manifest.json`` records
the official source URL, retrieval timestamp, exact fixture SHA-256, parser,
and hand-verified metadata. Each publisher matrix covers multiple authors,
shared affiliations, and multiple affiliations per author; unsupported and
block pages are covered separately.

To refresh a fixture:

#. Retrieve the official publisher page with a transparent user agent.
#. Independently verify every expected field against the official page.
#. Reduce the saved page to metadata-bearing current-layout markup without
   changing its values.
#. Update its UTC retrieval timestamp and SHA-256 in ``manifest.json``.
#. Run ``pytest -q`` and review parser changes independently from fixture
   expectations.

Never change parsing semantics merely to make a fixture expectation pass.

Database recreation
-------------------

The SQLite schemas are disposable and explicitly typed, with primary keys,
case-insensitive DOI uniqueness, status constraints, JSON collection columns,
provenance, and diagnostics. There are no migrations and no compatibility
guarantees for databases created by older versions.

Before using a new schema, back up any data that must be retained, remove only
the exact ``jobs.db`` and ``pub.db`` files in the configured appeer data
directory, then run ``appeer init`` to recreate them. Never delete a broad or
unverified path.
