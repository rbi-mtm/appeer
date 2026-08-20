"""Isolated initialize, parse, commit, and query baseline."""

import json
from pathlib import Path

from appeer.db.jobs_db import JobsDB
from appeer.db.pub_db import PubDB
from appeer.parse.default_metadata import default_metadata
from appeer.parse.metadata import PROVENANCE_FIELDS
from appeer.parse.parsers.NAT.parser_NAT_ANY_txt import Parser_NAT_ANY_txt
from appeer.pub.researcher import PubReSearcher


FIXTURES = Path(__file__).parent / 'fixtures'


def record_parse(database, label, parser):
    database.parses.add_entry(
        label=label,
        action_index=0,
        scrape_label=None,
        scrape_action_index=None,
        date='20260820-080000',
        input_file=str(FIXTURES / 'nature_current_article.html'),
    )
    for field, value in parser.metadata.items():
        if value is not None:
            database.parses.update_entry(
                label=label, action_index=0,
                column_name=field, new_value=value)
    for field, value in parser.provenance.items():
        if value is not None:
            database.parses.update_entry(
                label=label, action_index=0,
                column_name=field, new_value=value)
    database.parses.update_entry(
        label=label, action_index=0,
        column_name='success', new_value='T' if parser.success else 'F')
    database.parses.update_entry(
        label=label, action_index=0, column_name='status', new_value='X')
    return database.parses.get_action(label, 0)


def test_initialize_parse_commit_query_and_failed_parse_isolation(tmp_path):
    jobs_path = tmp_path / 'jobs.db'
    pub_path = tmp_path / 'pub.db'
    jobs = JobsDB(db_path=jobs_path)
    publications = PubDB(db_path=pub_path)
    jobs.create_database()
    publications.create_database()

    parser = Parser_NAT_ANY_txt(str(FIXTURES / 'nature_current_article.html'))
    parsed = record_parse(jobs, 'valid_parse', parser)

    assert parsed.raw_sha256 == parser.provenance['raw_sha256']
    assert json.loads(parsed.invalid_fields) == []
    assert json.loads(parsed.warnings) == []
    assert [entry.label for entry in jobs.parses.uncommitted] == ['valid_parse']

    commit_metadata = {
        field: getattr(parsed, field)
        for field in default_metadata() + list(PROVENANCE_FIELDS)
    }
    jobs.commits.add_entry(
        label='baseline_commit',
        action_index=0,
        parse_label='valid_parse',
        parse_action_index=0,
        date='20260820-080100',
        **commit_metadata,
    )
    duplicate, inserted = publications.pub.add_entry(**commit_metadata)
    assert (duplicate, inserted) == (False, True)

    broken_file = tmp_path / 'broken.html'
    broken_file.write_text(
        (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
        .replace('10.1038/s41598-025-92476-w', 'invalid DOI'),
        encoding='utf-8',
    )
    failed_parser = Parser_NAT_ANY_txt(str(broken_file))
    failed = record_parse(jobs, 'failed_parse', failed_parser)

    assert failed.success == 'F'
    assert failed.title.startswith('Chlorhexidine solutions')
    assert json.loads(failed.author_names) == [
        ['Aiping Deng'], ['Fangli Xiong'], ['Qiuping Ren']]
    assert 'doi' in json.loads(failed.invalid_fields)
    assert [entry.label for entry in jobs.parses.uncommitted] == ['valid_parse']
    assert publications.connection.execute(
        'SELECT COUNT(*) FROM pub').fetchone()[0] == 1

    stored = publications.pub.get_pub(parser.doi)
    assert stored.raw_sha256 == parser.provenance['raw_sha256']
    assert stored.parser == 'Parser_NAT_ANY_txt'
    assert stored.package_version
    assert stored.parsed_at
    assert stored.warnings == []
    jobs.close()
    publications.close()

    with PubReSearcher(db_path=pub_path) as researcher:
        researcher.search_pub(get_title=True, get_author_names=True)
        assert len(researcher.filtered_pubs) == 1
        assert researcher.filtered_pubs[0].doi == parser.doi
        assert researcher.filtered_pubs[0].author_names == parser.author_names
        assert researcher.analyzer.basic_search_results['warning_count'] == 0
