"""Offline command-line smoke and initialization guidance tests."""

import json
from pathlib import Path

from click.testing import CliRunner

from appeer.db.pub_db import PubDB
from appeer.general.config import Config


FIXTURES = Path(__file__).parent / 'fixtures'


def test_help_smoke_and_preinitialization_error_has_guidance():
    from appeer.cli import appeer_cli

    runner = CliRunner()
    help_result = runner.invoke(appeer_cli, ['--help'])
    assert help_result.exit_code == 0
    assert 'Commands:' in help_result.output

    result = runner.invoke(appeer_cli, ['pub', '--publisher_list'])
    assert result.exit_code == 1
    assert 'run `appeer init` first' in result.output
    assert 'Traceback' not in result.output


def test_cli_writes_documented_json_with_author_names(tmp_path):
    config = Config()
    config_path = Path(config._config_path)  # pylint: disable=protected-access
    data_root = tmp_path / 'appeer-data'
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '[GlobalSettings]\n'
        f'data_directory = {data_root}\n\n'
        '[ScrapeDefaults]\n'
        'sleep_time = 0\n'
        'max_tries = 1\n'
        'retry_sleep_time = 0\n'
        '429_sleep_time = 0\n',
        encoding='utf-8',
    )

    manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    metadata = manifest['nature_current_article.html']['expected']
    database = PubDB()
    database.create_database()
    database.pub.add_entry(**metadata)
    database.close()

    from appeer.cli import appeer_cli

    output = tmp_path / 'results.json'
    result = CliRunner().invoke(appeer_cli, [
        'pub', 'search', '--publisher', 'Nature Portfolio',
        '--get_author_names', '--output', str(output),
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload[0]['author_names'] == [
        'Aiping Deng', 'Fangli Xiong', 'Qiuping Ren']
