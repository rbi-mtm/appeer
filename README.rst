appeer
======

``appeer`` is a command-line tool for collecting publication metadata and
exploring how long peer review takes. It currently supports articles from the
Royal Society of Chemistry and Nature Portfolio.

The project is experimental and supports current article pages only.

Installation
------------

``appeer`` requires Python 3.13 or newer. From the project directory, run:

.. code:: shell

   python -m pip install .
   appeer init

Quick start
-----------

Create a text file containing one article URL or DOI per line:

.. code:: text

   10.1039/D3OB00424D
   https://www.nature.com/articles/s41598-025-92476-w

Then collect, process, and save the publication data:

.. code:: shell

   appeer scrape publications.txt
   appeer parse
   appeer commit

Search publications
-------------------

Print a summary of all saved publications:

.. code:: shell

   appeer pub search

Filter by date and export the results as JSON:

.. code:: shell

   appeer pub search --min_received 2024 --max_received 2025 \
       --get_title --get_author_names --output publications.json

Dates may be written as ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``. Searches can
also be filtered by publisher, journal, publication type, acceptance date, and
publication date.

Input files
-----------

``appeer scrape`` accepts:

* a text file containing one URL or DOI per line;
* a Publish or Perish JSON export containing article URLs.

Only complete, valid publication records are added to search results. Unusual
or incomplete records remain available for review without affecting summary
statistics.

Help
----

Use ``--help`` to see the available commands and options:

.. code:: shell

   appeer --help
   appeer scrape --help
   appeer pub search --help

If a command says that ``appeer`` has not been initialized, run ``appeer init``.
