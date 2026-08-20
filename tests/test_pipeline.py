"""Actual offline initialize, parse, commit, and query workflow."""

import json
from pathlib import Path

from click.testing import CliRunner

from appeer.cli import appeer_cli
from appeer.db.jobs_db import JobsDB
from appeer.db.pub_db import PubDB


FIXTURES = Path(__file__).parent / 'fixtures'


def test_cli_pipeline_commits_only_complete_successful_parses(tmp_path):
    broken = tmp_path / 'broken.html'
    broken.write_text(
        (FIXTURES / 'nature_current_article.html').read_text(encoding='utf-8')
        .replace('10.1038/s41598-025-92476-w', 'invalid DOI'),
        encoding='utf-8',
    )

    runner = CliRunner()
    initialized = runner.invoke(appeer_cli, ['init'], input='\n')
    assert initialized.exit_code == 0, initialized.output

    parsed = runner.invoke(appeer_cli, [
        'parse', '-F',
        str(FIXTURES / 'nature_current_article.html'), str(broken),
        '--job_label', 'pipeline_parse',
    ])
    assert parsed.exit_code == 0, parsed.output
    assert 'SQLite objects created in a thread' not in parsed.output

    with JobsDB() as jobs:
        actions = jobs.parses.get_actions_by_label('pipeline_parse')
        assert [action.success for action in actions] == ['T', 'F']
        assert actions[1].title.startswith('Chlorhexidine solutions')
        assert 'doi' in json.loads(actions[1].invalid_fields)
        assert actions[1].raw_sha256

    committed = runner.invoke(appeer_cli, [
        'commit', '-P', 'pipeline_parse',
        '--job_label', 'pipeline_commit',
    ])
    assert committed.exit_code == 0, committed.output

    with PubDB(read_only=True) as publications:
        rows = publications.pub.entries
        assert len(rows) == 1
        assert rows[0].doi == '10.1038/s41598-025-92476-w'
        assert rows[0].raw_sha256
        assert rows[0].parser == 'Parser_NAT_ANY_txt'

    output = tmp_path / 'publications.json'
    searched = runner.invoke(appeer_cli, [
        'pub', 'search', '--get_title', '--get_author_names',
        '--output', str(output),
    ])
    assert searched.exit_code == 0, searched.output
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert len(payload) == 1
    assert payload[0]['doi'] == '10.1038/s41598-025-92476-w'
    assert payload[0]['author_names'] == [
        'Aiping Deng', 'Fangli Xiong', 'Qiuping Ren']
