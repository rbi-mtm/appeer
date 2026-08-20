"""Base abstract class for an appeer batch job"""

import os
import abc
import click

from appeer.general.datadir import Datadir
from appeer.general import utils
from appeer.general import log as _log

from appeer.db.jobs_db import JobsDB
from appeer.db.tables.registered_tables import get_registered_tables

from appeer.jobs.db_properties import JobProperty

from appeer.scrape.scrape_action import ScrapeAction
from appeer.parse.parse_action import ParseAction
from appeer.commit.commit_action import CommitAction

from appeer.scrape import scrape_reports
from appeer.parse import parse_reports
from appeer.commit import commit_reports

def _validate_job_label(label):
    """
    Raises an error if the job ``label`` is invalid

    Parameters
    ----------
    label : str
        A string without whitespace

    """

    if not isinstance(label, str):
        raise ValueError('Job label must be a string.')

    if ' ' in label:
        raise ValueError('Job label must a single word (no whitespace allowed).')

class Job(abc.ABC):
    """
    Base abstract class for an appeer job

    """

    def __init_subclass__(cls, job_type):
        """
        Ensures that every Job subclass defines a ``job_type`` correctly

        Parameters
        ----------
        job_type : str
            Must be in ('scrape_job', 'parse_job', 'commit_job')

        """

        if job_type not in ('scrape_job', 'parse_job', 'commit_job'):
            raise ValueError('Invalid job type specified: must be in ("scrape_job", "parse_job", "commit_job")')

        cls._job_type = job_type

    def __setattr__(self, name, value):
        """
        Ensures the job label and job mode are safely set

        """

        if name == 'label':

            if value:
                _validate_job_label(label=value)

        if name == '_job_mode':

            if value not in ('read', 'write'):
                raise ValueError('Job mode must be "read" or "write".')

        super().__setattr__(name, value)

    @classmethod
    def _define_db_properties(cls, job_fields):
        """
        Gets the current values of a job entry

        """

        job_fields.remove('label')

        for field in job_fields:

            prop = JobProperty(field)
            setattr(cls, field, prop)

    def __init__(self, label=None, job_mode='read'):
        """
        Connects to the jobs database and sets the job label

        If the job already exists, current values in the job entry
            are read from the database

        If ``job_mode == 'read'``, the job attributes cannot be modified

        If ``job_mode == 'write'``, the job attributes can be modified and
            the corresponding entry in the jobs database will be modified
            as well

        Parameters
        ----------
        label : str
            Unique job label
        job_mode : str
            Must be 'read' or 'write'

        """

        self.label = label
        self._job_mode = job_mode

        job_fields = get_registered_tables()[f'{self._job_type}s']

        Job._define_db_properties(job_fields=job_fields)

        self.__job_lab = self._job_type.split('_')[0]
        self.__date = None
        self._logger = None

        self._queue = None
        self._db = JobsDB()
        self._log_path = None
        if self.label and self._db._db_exists: #pylint:disable=protected-access
            entry = self._job_entry
            if entry:
                self._log_path = entry.log

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    @property
    def _job_exists(self):
        """
        Checks whether the job with ``self.label`` exists in the database

        """

        exists = False

        if not self._db._db_exists: #pylint:disable=protected-access
            raise RuntimeError('appeer is not initialized; run `appeer init` first.')
        if not self.label:
            exists = False

        else:

            match self._job_type:

                case 'scrape_job':
                    exists = self._db.scrape_jobs.job_exists(self.label)

                case 'parse_job':
                    exists = self._db.parse_jobs.job_exists(self.label)

                case 'commit_job':
                    exists = self._db.commit_jobs.job_exists(self.label)

        return exists

    @property
    def _job_entry(self):
        """
        Gets the current entry with ``self.label`` in the jobs database

        """

        _job = None

        if not self._job_exists:

            click.echo(f'The job with label "{self.label}" does not exist')

        else:

            match self._job_type:

                case 'scrape_job':
                    _job = self._db.scrape_jobs.get_job(self.label)

                case 'parse_job':
                    _job = self._db.parse_jobs.get_job(self.label)

                case 'commit_job':
                    _job = self._db.commit_jobs.get_job(self.label)

        return _job

    @_job_entry.setter
    def _job_entry(self, value):
        """
        This attribute should not be directly set

        """

        raise PermissionError('Cannot directly set the "_job_entry"` attribute')

    @property
    def actions(self):
        """
        Get actions for the current job label

        Returns
        -------
        _actions : list
            List of ScrapeActions corresponding to the current job label

        """

        _actions = []

        if not self._job_exists:
            _actions = []

        else:

            match self._job_type:

                case 'scrape_job':

                    __scrape_entries = self._db.scrape_jobs.get_actions(
                            label=self.label)

                    _actions = [ScrapeAction(label=entry.label,
                        action_index=entry.action_index, _db=self._db)
                        for entry in __scrape_entries]

                case 'parse_job':

                    __parse_entries = self._db.parse_jobs.get_actions(
                            label=self.label)

                    _actions = [ParseAction(label=entry.label,
                        action_index=entry.action_index, _db=self._db)
                        for entry in __parse_entries]

                case 'commit_job':

                    __commit_entries = self._db.commit_jobs.get_actions(
                            label=self.label)

                    _actions = [CommitAction(label=entry.label,
                        action_index=entry.action_index, _db=self._db)
                        for entry in __commit_entries]

            _actions.sort(key=lambda x: x.action_index)

        return _actions

    @property
    def failed_actions(self):
        """
        Get actions for which ``action.success == 'F'``

        Returns
        -------
        _failed_actions : list
            List of failed actions

        """

        _failed_actions = [action for action in self.actions
                if action.success == 'F']

        return _failed_actions

    @property
    def successful_actions(self):
        """
        Get actions for which ``action.success == 'T'``

        Returns
        -------
        _successful_actions : list
            List of successful actions

        """

        _successful_actions = [action for action in self.actions
                if action.success == 'T']

        return _successful_actions

    def _qualify_job_label(self, label=None):
        """
        Prepares a label for a new job

        If ``label`` is not given, a random default is generated
        The ``label`` is then set to ``self.label``

        Parameters
        ----------
        label : str
            Optional label of the new job; if not given, it is generated

        """

        date = utils.get_current_datetime()
        random_number = utils.random_number()

        if not label:

            label = f'{self.__job_lab}_{date}_{random_number}'

        self.label = label

        if self._job_exists:
            raise PermissionError(f'Job with label "{self.label}" already exists.')

        self.__date = date

    def new_job(self, **kwargs):
        """ 
        Create a new job

        A number of options may be provided through keyword arguments (see
            below). If not provided, defaults are generated by the
            implementation of _prepare_new_job_parameters(self, **kwargs)

        Keyword Arguments (scrape_job)
        ------------------------------
        label : str
            Unique job label
        description : str
            Optional job description
        log_directory : str
            Directory into which to store the log file
        download_directory : str
            Directory into which to download the data
        zip_file : str
            Path to the output ZIP file

        Keyword Arguments (parse_job)
        -----------------------------
        label : str
            Unique job label
        description : str
            Optional job description
        log_directory : str
            Directory into which to store the log file
        parse_directory : str
            Directory into which to (temporarily) create files for parsing
        mode : str
            Parsing mode; one of ('E', 'A', 'S', F); 'A' is default; mutable

        """

        self._job_mode = 'write'

        kwargs.setdefault('label', None)
        self._qualify_job_label(kwargs['label'])

        job_parameters = self._prepare_new_job_parameters(**kwargs)

        self._initialize_job_common(**job_parameters)

        self._wlog(_log.get_logo())

        match self._job_type:

            case 'scrape_job':
                self._wlog(scrape_reports.scrape_general_report(job=self))

            case 'parse_job':
                self._wlog(parse_reports.parse_general_report(job=self))

            case 'commit_job':
                self._wlog(commit_reports.commit_general_report(job=self))

    @abc.abstractmethod
    def _prepare_new_job_parameters(self, **kwargs):
        """
        Adds defaults to **kwargs inputted to ``self.new_job(**kwargs)``

        Returns
        -------
        job_arguments : dict
            The inputted keyword arguments with added defaults

        """

    def _initialize_job_common(self,
                     description=None,
                     log_directory=None,
                     **kwargs):
        """
        The part of ``appeer`` job initialization common to all job types

        If ``description`` is not given, it is set to 'No description'

        If ``log_directory`` is not given, a default value is generated

        Parameters
        ----------
        description : str
            Optional job description
        log_directory : str
            Optional path to the directory in which to store the log file
        kwargs : *
            Keyword arguments dependent on the job type

        """

        if self._job_mode != 'write':
            raise PermissionError('Cannot initialize new job in "read" mode of the Job subclass.')

        if not self.label:
            raise AssertionError('Cannot initialize a new job; self.label is not set.')

        if self._job_exists:
            raise PermissionError(f'Cannot initialize a new job; the job with label "{self.label}" already exists.')

        if not description:
            description = 'No description'

        if not log_directory:

            data_dir = Datadir()
            log_directory = getattr(data_dir, f'{self.__job_lab}_logs')

        log_name = f'{self.label}.log'
        log_path = utils.abspath(os.path.join(log_directory, log_name))

        self._initialize_db_entry(description=description,
                date=self.__date,
                log_path=log_path,
                **kwargs)
        self._log_path = log_path

    def _initialize_db_entry(self, description, date, log_path, **kwargs):
        """
        Initializes an entry in the corresponding jobs table

        Parameters
        ----------
        description : str
            Job description
        date : str
            Date and time of the job start
        log_path : str
            Path to the log file
        kwargs : *
            Keyword arguments dependent on the job type

        """

        if self._job_exists:
            raise PermissionError(f'Cannot add job entry to the database; the job with label "{self.label}" already exists.')

        match self._job_type:

            case 'scrape_job':
                self._db.scrape_jobs.add_entry(label=self.label,
                        description=description,
                        log_path=log_path,
                        date=date,
                        **kwargs)

            case 'parse_job':
                self._db.parse_jobs.add_entry(label=self.label,
                        description=description,
                        log_path=log_path,
                        date=date,
                        **kwargs)

            case 'commit_job':
                self._db.commit_jobs.add_entry(label=self.label,
                        description=description,
                        log_path=log_path,
                        date=date,
                        **kwargs)

    def _wlog(self, text):
        """
        Writes to the ``self.log`` file through the logger object

        Parameters
        ----------
        text : str
            Text to be written in the log file

        """

        log_path = self._log_path
        if log_path is None:
            log_path = self.log
            self._log_path = log_path
        _logger = _log.init_logger(log_path=log_path, log_name=self.label)
        _logger.info(text)

    def _log_server(self):
        """
        Log messages received from actions through self._queue

        """

        if not self._queue:
            raise ValueError('Cannot log action message; self._queue has not been initialized.')

        while True:

            message = self._queue.get()
            self._wlog(message)
            self._queue.task_done()
