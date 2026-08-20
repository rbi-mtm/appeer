"""Deterministic SQLite ownership, rollback, and resume tests."""

import json
import sqlite3
from pathlib import Path

import pytest

from appeer.db.jobs_db import JobsDB
from appeer.db.pub_db import PubDB


FIXTURES = Path(__file__).parent / 'fixtures'


def nature_metadata():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    return manifest['nature_current_article.html']['expected'].copy()


def test_database_owns_stable_tables_and_closes_exact_connection(tmp_path):
    database = PubDB(db_path=tmp_path / 'pub.db')
    database.create_database()

    table = database.pub
    connection = database.connection
    assert database.pub is table
    assert table._con is connection  # pylint: disable=protected-access

    database.close()
    assert database.closed
    database.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute('SELECT 1')


def test_context_manager_closes_connection(tmp_path):
    path = tmp_path / 'pub.db'
    database = PubDB(db_path=path)
    database.create_database()
    database.close()

    with PubDB(db_path=path) as reopened:
        connection = reopened.connection
        assert connection.execute('SELECT COUNT(*) FROM pub').fetchone()[0] == 0

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute('SELECT 1')


def test_pub_duplicate_handling_and_json_boundary(tmp_path):
    database = PubDB(db_path=tmp_path / 'pub.db')
    database.create_database()
    metadata = nature_metadata()

    assert database.pub.add_entry(**metadata) == (False, True)
    assert database.pub.add_entry(**metadata) == (True, False)

    replacement = metadata | {'title': 'Corrected title'}
    assert database.pub.add_entry(overwrite=True, **replacement) == (True, True)
    stored = database.pub.get_pub(metadata['doi'])
    assert stored.title == 'Corrected title'
    assert stored.author_names == metadata['author_names']
    assert stored.affiliations == metadata['affiliations']
    database.close()


def test_failed_pub_write_rolls_back(tmp_path):
    database = PubDB(db_path=tmp_path / 'pub.db')
    database.create_database()
    metadata = nature_metadata() | {'title': object()}

    with pytest.raises(sqlite3.ProgrammingError):
        database.pub.add_entry(**metadata)

    assert database.connection.execute('SELECT COUNT(*) FROM pub').fetchone()[0] == 0
    assert not database.connection.in_transaction
    database.close()


def test_job_checkpoint_survives_reopen_and_interrupted_update_rolls_back(tmp_path):
    path = tmp_path / 'jobs.db'
    database = JobsDB(db_path=path)
    database.create_database()
    database.scrape_jobs.add_entry(
        label='resume_test',
        date='20260820-080000',
        description='resume baseline',
        log_path=str(tmp_path / 'resume.log'),
        download_directory=str(tmp_path / 'downloads'),
        zip_file=str(tmp_path / 'archive.zip'),
    )
    database.scrape_jobs.update_entry(
        label='resume_test', column_name='job_step', new_value=2)
    database.close()

    reopened = JobsDB(db_path=path)
    assert reopened.scrape_jobs.get_job('resume_test').job_step == 2

    with pytest.raises(RuntimeError), reopened.transaction() as connection:
        connection.execute(
            'UPDATE scrape_jobs SET job_step = 3 WHERE label = ?',
            ('resume_test',),
        )
        raise RuntimeError('simulated interruption')

    assert reopened.scrape_jobs.get_job('resume_test').job_step == 2
    reopened.close()
