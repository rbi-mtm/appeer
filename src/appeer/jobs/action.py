"""Base abstract class for an appeer action"""

import abc
import click

from appeer.general import utils
from appeer.general import log as _log

from appeer.db.jobs_db import JobsDB
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.jobs.db_properties import ActionProperty

def _validate_action_label(label):
    """
    Raises an error if the action ``label`` is invalid

    Parameters
    ----------
    label : str
        A string without whitespace

    """

    if not isinstance(label, str):
        raise ValueError('Action label must be a string.')

    if ' ' in label:
        raise ValueError('Action label must a single word (no whitespace allowed).')

def _validate_action_index(action_index):
    """
    Raises an error if the ``action_index`` is invalid

    Parameters
    ----------
    action_index : int
        Non-negative integer

    """

    if not isinstance(action_index, int):
        raise ValueError('Action index must be an integer.')

    if not action_index >= 0:
        raise ValueError('Action index must a non-negative integer.')

class Action(abc.ABC):
    """
    Base abstract class for an appeer action

    """

    def __init_subclass__(cls, action_type):
        """
        Ensures that every Action subclass defines a ``action_type`` correctly

        Parameters
        ----------
        action_type : str
            Must be in ('scrape', 'parse', 'commit')

        """

        if action_type not in ('scrape', 'parse', 'commit'):
            raise ValueError('Invalid action type specified: must be in ("scrape", "parse", "commit")')

        cls._action_type = action_type

    def __setattr__(self, name, value):
        """
        Ensures the action label, index mode are safely set

        """

        if name == 'label':

            if value:
                _validate_action_label(label=value)

        if name == 'action_index':

            if value:
                _validate_action_index(action_index=value)

        if name == '_action_mode':

            if value not in ('read', 'write'):
                raise ValueError('Action mode must be "read" or "write".')

        super().__setattr__(name, value)

    @classmethod
    def _define_db_properties(cls, action_fields):
        """
        Gets the current values of a action entry

        """

        action_fields.remove('label')
        action_fields.remove('action_index')

        for field in action_fields:

            prop = ActionProperty(field)
            setattr(cls, field, prop)

    def __init__(self, label=None, action_index=None, action_mode='read'):
        """
        Connects to the jobs database and sets the action label and index

        If the action already exists, current values in the action entry
            are read from the database

        If ``action_mode == 'read'``, the action attributes cannot be modified

        If ``action_mode == 'write'``, the action attributes can be modified
            and the corresponding entry in the actions database will be
            modified as well

        Parameters
        ----------
        label : str
            Unique action label
        action_mode : str
            Must be 'read' or 'write'

        """

        self.label = label
        self.action_index = action_index

        self._action_mode = action_mode

        action_fields = get_registered_tables()[f'{self._action_type}s']

        Action._define_db_properties(action_fields=action_fields)

        self._queue = None
        self._db = JobsDB()

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    @property
    def _action_exists(self):
        """
        Checks whether the action with ``self.label`` exists in the database

        """

        exists = False

        if not self._db._db_exists: #pylint:disable=protected-access
            raise RuntimeError('appeer is not initialized; run `appeer init` first.')
        if not self.label:
            exists = False

        if self.action_index is None:
            exists = False

        else:

            match self._action_type:

                case 'scrape':
                    exists = self._db.scrapes.action_exists(self.label,
                            self.action_index)

                case 'parse':
                    exists = self._db.parses.action_exists(self.label,
                            self.action_index)

                case 'commit':
                    exists = self._db.commits.action_exists(self.label,
                            self.action_index)

        return exists

    @property
    def _action_entry(self):
        """
        Gets the current entry with ``self.label`` and
            ``self.action_index`` in the actions database

        """

        _action = None

        if not self._action_exists:

            click.echo(f'The action with label "{self.label}" and index {self.action_index} does not exist')

        else:

            match self._action_type:

                case 'scrape':
                    _action = self._db.scrapes.get_action(self.label,
                            self.action_index)

                case 'parse':
                    _action = self._db.parses.get_action(self.label,
                            self.action_index)

                case 'commit':
                    _action = self._db.commits.get_action(self.label,
                            self.action_index)

        return _action

    @_action_entry.setter
    def _action_entry(self, value):
        """
        This attribute should not be directly set

        """

        raise PermissionError('Cannot directly set the "_action_entry"` attribute')

    def _initialize_action_common(self, **kwargs):
        """
        The part of ``appeer`` action initialization common to all action types

        Parameters
        ----------
        kwargs : *
            Keyword arguments dependent on the action type

        """

        date = utils.get_current_datetime()

        if self._action_mode != 'write':
            raise PermissionError('Cannot initialize new action in "read" mode of the Action subclass.')

        if not self.label:
            raise AssertionError('Cannot initialize a new action; self.label is not set.')
        if self.action_index is None:
            raise AssertionError('Cannot initialize a new action; self.action_index is not set.')

        if self._action_exists:
            raise PermissionError(f'Cannot initialize a new action; the action with label "{self.label}" and index={self.action_index} already exists.')

        self._initialize_db_entry(date=date, **kwargs)

    def _initialize_db_entry(self, date, **kwargs):
        """
        Initializes an entry in the corresponding actions table

        Parameters
        ----------
        date : str
            Date and time of the action initialization
        kwargs : dict
            Keyword arguments dependent on the action type

        """

        if self._action_exists:
            raise PermissionError(f'Cannot add action entry to the database; the action with label "{self.label}" and index={self.action_index} already exists.')

        match self._action_type:

            case 'scrape':
                self._db.scrapes.add_entry(label=self.label,
                        action_index=self.action_index,
                        date=date,
                        **kwargs)

            case 'parse':
                self._db.parses.add_entry(label=self.label,
                        action_index=self.action_index,
                        date=date,
                        **kwargs)

            case 'commit':
                self._db.commits.add_entry(label=self.label,
                        action_index=self.action_index,
                        date=date,
                        **kwargs)

    def _aprint(self, message):
        """
        Prints a ``message`` to stdout or puts it in the queue
        
        If the message is put into the queue, it will be logged in
            the job log file

        Parameters
        ----------
        message : str
            String to be printed to stdout or logged in the job log file

        """

        if self._queue:
            self._queue.put(message)

        else:
            click.echo(message)
