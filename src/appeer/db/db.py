"""Connection-owning base class for appeer SQLite databases."""

import abc
from contextlib import contextmanager
import importlib
import os
import sqlite3

import click

from appeer.general import log
from appeer.general.datadir import Datadir
from appeer.db.tables.registered_tables import get_registered_tables


class ManagedConnection(sqlite3.Connection):
    """Defer incidental table commits while a logical transaction is active."""

    def commit(self):
        if getattr(self, '_appeer_transaction_depth', 0) == 0:
            super().commit()

    def force_commit(self):
        """Commit regardless of the logical transaction depth."""

        super().commit()

    def rollback(self):
        if getattr(self, '_appeer_transaction_depth', 0) == 0:
            super().rollback()

    def force_rollback(self):
        """Roll back regardless of the logical transaction depth."""

        super().rollback()


class DB(abc.ABC):
    """Own exactly one SQLite connection and stable table interfaces."""

    def __init_subclass__(cls, tables):
        if not isinstance(tables, list):
            raise TypeError('Tables must be given as a list.')
        allowed = get_registered_tables()
        if any(not isinstance(table, str) or table not in allowed
               for table in tables):
            raise PermissionError(f'Unknown table in {tables}.')

        cls.tables = tuple(tables)
        cls._table_classes = {}
        for table in tables:
            module = importlib.import_module(f'appeer.db.tables.{table}')
            class_name = ''.join(word.capitalize() for word in table.split('_'))
            cls._table_classes[table] = getattr(module, class_name)

    def __init__(self, db_type, read_only=False, db_path=None):
        if db_type not in ('jobs', 'pub'):
            raise ValueError('db_type must be "jobs" or "pub".')

        self._db_type = db_type
        self._read_only = read_only
        self._con = None
        self._cur = None
        self._closed = True
        self._dashes = log.get_log_dashes()

        if db_path is None:
            try:
                datadir = Datadir()
            except (KeyError, TypeError) as exc:
                raise RuntimeError(
                    'appeer is not initialized; run `appeer init` first.') from exc
            self._base = datadir.base
            self._db_path = os.path.join(datadir.db, f'{db_type}.db')
        else:
            self._db_path = os.fspath(db_path)
            self._base = os.path.dirname(os.path.dirname(self._db_path))

        if self._db_exists:
            self._connect()
        elif self._read_only:
            if db_path is None:
                raise RuntimeError(
                    'appeer is not initialized; run `appeer init` first.')
            raise FileNotFoundError(self._db_path)

    @property
    def _db_exists(self):
        return os.path.isfile(self._db_path)

    @property
    def closed(self):
        return self._closed

    @property
    def connection(self):
        if self._con is None or self._closed:
            raise sqlite3.ProgrammingError('The database connection is closed.')
        return self._con

    def _connect(self):
        if self._con is not None and not self._closed:
            return
        target = self._db_path
        if self._read_only:
            target = f'file:{os.path.abspath(target)}?mode=ro'
        self._con = sqlite3.connect(
            target, uri=self._read_only, factory=ManagedConnection)
        self._con._appeer_transaction_depth = 0
        self._cur = self._con.cursor()
        self._closed = False
        for table_name, table_class in self._table_classes.items():
            setattr(self, table_name, table_class(self._con))

    def close(self):
        """Close the owned connection. Calling twice is safe."""

        if self._con is not None and not self._closed:
            self._con.close()
        self._closed = True

    def __enter__(self):
        if self._con is None or self._closed:
            if not self._db_exists:
                raise FileNotFoundError(self._db_path)
            self._connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and self._con is not None:
            self._con.force_rollback()
        self.close()
        return False

    @contextmanager
    def transaction(self):
        """Commit one logical state change or roll it back on failure."""

        connection = self.connection
        outermost = connection._appeer_transaction_depth == 0
        connection._appeer_transaction_depth += 1
        try:
            yield connection
        except BaseException:
            if outermost:
                connection.force_rollback()
            raise
        else:
            if outermost:
                connection.force_commit()
        finally:
            connection._appeer_transaction_depth -= 1

    def create_database(self):
        """Create and initialize a disposable database if absent."""

        if self._read_only:
            raise PermissionError('Cannot create a database in read-only mode.')
        if self._db_exists:
            click.echo(f'WARNING: {self._db_type} database already exists at {self._db_path}')
            click.echo(self._dashes)
            self._handle_database_exists()
            if self._closed:
                self._connect()
            return

        parent = os.path.dirname(os.path.abspath(self._db_path))
        os.makedirs(parent, exist_ok=True)
        self._connect()
        try:
            with self.transaction():
                for table in self.tables:
                    getattr(self, table).initialize_table(commit=False)
        except BaseException:
            self.close()
            raise
        click.echo(f'{self._db_type} database initialized at {self._db_path}')

    def _handle_database_exists(self):
        proceed = log.ask_yes_no(
            f'Do you want to proceed with the current {self._db_type} database? [Y/n]\n')
        if proceed == 'Y':
            click.echo(f'Proceeding with the current {self._db_type} database.')
        else:
            click.echo('Stopping, as requested.')
            raise RuntimeError('Database creation cancelled.')
