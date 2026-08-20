# Repository working agreement

## Required commands

Run these commands from the repository root:

- Install for development and tests: `python -m pip install -e '.[test]'`
- Compile Python sources: `python -m compileall -q src`
- Run the offline suite: `pytest -q`
- Run opt-in live/slow checks: `pytest -q --runslow`
- Run an isolated CLI smoke test: `tmpdir="$(mktemp -d)"; XDG_CONFIG_HOME="$tmpdir/config" XDG_DATA_HOME="$tmpdir/data" XDG_CACHE_HOME="$tmpdir/cache" appeer --help`
- Build a wheel: `python -m pip wheel --no-deps --wheel-dir dist .`

The default test suite must be offline. Tests that contact publishers or any other
external service must be marked `slow` and run only when explicitly requested.

## Python and change style

Follow the style already present in the file being changed. Keep changes focused
and readable; do not introduce unrelated formatting, import reordering, renaming,
or cleanup churn. Prefer explicit behavior and narrow publisher-specific parsing
over broad heuristics.

Never change parsing semantics merely to make a test pass. First independently
verify the fixture's source metadata and record the evidence used by the test.

## Architecture boundaries

- Scraping retrieves untrusted publisher input and records retrieval outcomes. It
  must not decide that an HTTP success is a valid article or write publications.
- Parsing reads immutable scraped input, extracts and validates metadata, and
  records diagnostics. It must not perform network requests or commit invalid or
  incomplete publications.
- Committing copies only successful, complete parses into the publication store in
  one atomic logical transaction. It must not reinterpret scraped HTML.
- Database modules own connection and transaction lifecycles. Callers must close
  the exact connection they use; failed writes must roll back while durable job
  checkpoints remain available for resume.

## Commits and delivery

Use the established commit subject format:
`SCOPE(|SCOPE): Imperative summary`.

Every commit must also have a concise body in plain words explaining what the
change does. Do not rely on the subject alone.

Make small, atomic commits containing one coherent, independently verified change.
Do not add `Co-authored-by` or any other AI-attribution trailers; the project handles
attribution separately. Never run `git push` without an explicit user instruction.
Do not rewrite or include unrelated user changes.

## Safety and robustness

Treat URLs, HTML, JSON, archive members, configuration, and database contents as
untrusted input. Parse hostnames and identifiers exactly, reject path traversal,
avoid shell interpolation, and never log secrets. Use a transparent configurable
user agent, obey publisher rate limits and `Retry-After`, and keep network access
out of default tests. Bound retries and timeouts.

Before destructive cleanup or database recreation, resolve and validate the exact
target and preserve user data unless recreation was explicitly requested. Never
use broad recursive deletion, unresolved globs, or repository-wide destructive Git
commands. Prefer temporary XDG directories in tests and smoke checks so developer
configuration and data cannot be modified.
