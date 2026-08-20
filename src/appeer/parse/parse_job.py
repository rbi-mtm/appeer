"""Parse scraped publications"""

import sys
import os
import threading
import queue
import inspect

from appeer.general.datadir import Datadir
from appeer.general import log as _log
from appeer.general import utils as _utils

from appeer.jobs.job import Job

from appeer.scrape.scrape_job import ScrapeJob

from appeer.parse.parse_action import ParseAction
from appeer.parse.parse_packer import ParsePacker
from appeer.parse import parse_reports as reports


class ParseJob(Job, job_type='parse_job'): #pylint:disable=too-many-instance-attributes
    """
    Parse scraped publications

    The ``mode`` attribute defines four available parsing modes:

        1) Auto (A) [DEFAULT]
            Parse files found through the ``scrape_jobs`` table,
            for the scrape jobs that were executed but not previously parsed.
            Note that only the scrape actions which were not previously parsed
            will be parsed. Default mode

        2) Everything (E) 
            Parse all files found through the ``scrape_jobs`` table, regardless
            of whether the jobs and the corresponding actions were previously
            parsed. Only executed jobs are considered

        3) Scrape job (S) 
            Parse a list of scrape jobs with the given labels, regardless of 
            whether the jobs and the corresponding actions were previously
            parsed

        4) File list (F) 
            Parse a list of files. This mode is independent of previous
            scrape jobs

    Instances of the ParseJob class have dynamically created properties
        corresponding to the columns of the ``parse_jobs`` table in the
        ``jobs`` database

        Some of these properties are mutable; changing their value will
        update the value in the ``jobs`` database. The values of the
        non-mutable properties are set using ``self.new_job(**kwargs)``.
        The values of these properties may be edited only if
        ``self._job_mode == 'write'

    List of the dynamically generated properties:

    Dynamic Properties
    ------------------
    date : str
        Job creation date and time
    description : str
        Optional job description
    log : str
        Path to the job log file
    parse_directory : str
        Directory into which to (temporarily) create files for parsing
    mode : str
        Parsing mode; one of ('A', 'E', 'S', 'F'); 'A' is default
    job_status : str
        Job status; one of ('I', 'W', 'R', 'E', 'X'); mutable
    job_step : int
        Index of the current job action; mutable
    job_successes : int
        Counts how many actions were succesfully ran; mutable
    job_fails : int
        Counts how many actions failed; mutable
    no_of_publications : int
        Counts how many publications were added to the job; mutable
    job_committed : str
        Whether all parsed data corresponding to the job is committed;
            one of ('T', 'F'); mutable

    """

    def __init__(self,
            label=None,
            job_mode='read'):
        """
        Connects to the job database and sets the job label

        Parameters
        ----------
        label : str
            Unique job label
        job_mode : str
            Must be 'read' or 'write'

        """

        super().__init__(label=label, job_mode=job_mode)

        self._publisher_journals_dict = {}

    @property
    def summary(self):
        """
        A formatted summary of the parse job

        Returns
        -------
        _summary : str
            Job summary

        """

        if not self._job_exists:
            _summary = f'Parse job {self.label} does not exist.'

        else:
            _summary = reports.parse_job_summary(job=self)

        return _summary

    def _prepare_new_job_parameters(self, **kwargs):
        """
        Set defaults and sanitize parameters passed to ``self.new_job()``

        Keyword Arguments
        -----------------
        description : str
            Optional job description
        log_directory : str
            Directory into which to store the log file
        parse_directory : str
            Directory into which to (temporarily) create files for parsing
        mode : str
            Parsing mode; one of ('A', 'E', 'S', 'F'); 'A' is default

        Returns
        -------
        job_arguments : dict
            The inputted keyword arguments with added defaults

        """

        datadir = Datadir()

        default_parse_directory = os.path.join(datadir.parse,
                self.label)
        kwargs.setdefault('parse_directory', default_parse_directory)

        if kwargs['parse_directory'] is None:
            kwargs['parse_directory'] = default_parse_directory

        kwargs['parse_directory'] = os.path.abspath(
                kwargs['parse_directory'])

        kwargs.setdefault('mode', 'A')

        kwargs.setdefault('description', None)
        kwargs.setdefault('log_directory', None)

        job_parameters = {
                'description': kwargs['description'],
                'parse_directory': kwargs['parse_directory'],
                'log_directory': kwargs['log_directory'],
                'mode': kwargs['mode']
                }

        return job_parameters

    def add_publications(self, data_source=None):
        """
        Add publications to be parsed

        Depending on the ``self.mode`` attribute, data_source may be:

            1) (A): None
            2) (E): None
            3) (S): List of scrape job labels
            4) (F): List of file paths

        Parameters
        ----------
        data_source : None | list of str
            None for modes ('A', 'E'), list of scrape job labels ('S'),
                list of file paths ('F')

        """

        if not self._job_exists:
            raise PermissionError('Cannot add publications to a parse job; most likely, the job has not yet been initialized.')

        if self.job_status == 'X':
            raise PermissionError(f'Cannot add new publications to the parse job "{self.label}"; the job has already been executed.')

        if self.job_status == 'R':
            raise PermissionError(f'Cannot add new publications to the parse job "{self.label}"; the job is in the "R" (Running) state.')

        if self.job_status == 'E':
            raise PermissionError(f'Cannot add new publications to the parse job "{self.label}"; the job is in the "E" (Error) state.')

        self._job_mode = 'write'

        self._queue = queue.Queue()
        threading.Thread(target=self._log_server, daemon=True).start()

        self._prepare_parsing(data_source=data_source)

        self._queue.join()

    def _prepare_parsing(self, data_source):
        """
        Prepare inputted data for parsing depending on the parsing mode

        Parameters
        ----------
        data_source : None | list of str
            None for modes ('A', 'E'), list of scrape job labels ('S'),
                list of file paths ('F')

        """

        self._wlog(_log.boxed_message('PREPARING PARSING', centered=True) + '\n')

        try:

            packer = ParsePacker(parse_mode=self.mode,
                    data_source=data_source,
                    parse_directory=self.parse_directory,
                    _queue=self._queue)

        except ValueError as err:
            self._wlog(err)

        else:

            packer.pack()

            if packer.success:
                self._queue.put(
                        f'\nPrepared {len(packer.packet)} files for parsing.')

                self._add_actions(parse_packet=packer.packet)

                self.no_of_publications = len(self.actions)
                self.job_status = 'W'

            else:
                self._queue.put('No new actions were added to the parse job.')

    def run_job(self, restart_mode='from_scratch', cleanup=False, **kwargs):
        """
        Runs the actions defined in self.actions

        If ``restart_mode == 'from_scratch'``, the ``job_step`` is set to 0
            and the parsing is performed for all the actions in the job.

        If ``restart_mode == 'resume'``, parsing is resumed from the current
            ``job_step``.

        If ``cleanup == 'True'``, the temporary directory given by
            ``self.parse_directory`` will be deleted at the end of the
            parse job

        If the keyword argument ``no_scrape_mark == True``, scrape jobs
            and actions corresponding to parse actions will not be labeled
            as parsed, even if parsing is successful.

            If ``no_scrape_mark == False``, scrape jobs and actions will
            be marked as parsed upon completion of the parse job.

        The appropriate parser for each input file is determined automatically
            by the Preparser class. This process may be accelerated by
            specifying the ``publishers``, ``journals`` and ``data_types``
            keyword arguments. For more details, see the documentation
            of the Preparser class.

        Parameters
        ----------
        restart_mode : str
            Must be in ('from_scratch', 'resume')
        cleanup : bool
            If True, delete the temporary parsing directory
                upon completion of the parse job

        Keyword Arguments
        -----------------
        no_scrape_mark : bool
            If True, scrape jobs will not be labeled as parsed
                even if they are parsed successfully
        publishers : str | list of str | None
            List of candidate parser publisher codes
        journals : str | list of str | None
            List of candidate parser journal codes
        data_types : str | list of str | None
            List of candidate parser data types;
                currently, only 'txt' is supported

        """

        if self.no_of_publications == 0:
            self._wlog(f'\nError: Cannot run parse job "{self.label}"; no publications were added to this job. Exiting.\n')
            self.job_status = 'E'
            sys.exit()

        run_parameters =\
                self._prepare_run_parameters(restart_mode=restart_mode,
                        cleanup=cleanup,
                        **kwargs)

        self._job_mode = 'write'

        if run_parameters['restart_mode'] == 'from_scratch':

            self.job_step = 0
            self.job_fails = 0
            self.job_successes = 0

        self.job_status = 'R'

        self._wlog(reports.parse_start_report(job=self,
            run_parameters=run_parameters))

        self._queue = queue.Queue()
        threading.Thread(target=self._log_server, daemon=True).start()

        parsers_dir = os.path.join(
                os.path.dirname(inspect.getfile(self.__class__)),
                'parsers'
                )

        publishers_index = _utils.load_json(
                os.path.join(parsers_dir, 'publishers_index.json')
                )

        action_parameters = {
                'publishers': run_parameters['publishers'],
                'journals': run_parameters['journals'],
                'data_types': run_parameters['data_types'],
                'publishers_index': publishers_index,
                'publisher_journals_dict': self._publisher_journals_dict
                }

        while self.job_step < self.no_of_publications:

            self.run_action(_queue=self._queue,
                    action_index=self.job_step,
                    **action_parameters)

            self.job_step += 1

        self._queue.join()

        if all(status == 'X' for status in
                (getattr(action, 'status') for action in self.actions)):

            self.job_status = 'X'

        self._wlog(reports.parse_end(job=self))

        if not run_parameters['no_scrape_mark']:
            self._update_scrapes()

        else:
            self._wlog('no_scrape_mark was set to True; no scrape job/actions will be marked as parsed.\n')

        if run_parameters['cleanup']:
            _utils.delete_directory(self.parse_directory, verbose=False)
            self._wlog(f'Cleanup requested; deleted {self.parse_directory}')

        else:
            self._wlog(f'Cleanup not requested; keeping {self.parse_directory}')

        self._wlog(reports.end_logo(job=self))

    def _add_actions(self, parse_packet):
        """
        Add ParseActions to the ParseJob

        ``parse_packet`` is given by ``appeer.parse.parse_packer.packet``

        Parameters
        ----------
        parse_packet : list of appeer.parse.parse_packer._ParseEntry
            Packet containing info on the filepaths to be parsed
                (and possibly scrape labels and action indices from which
                the files originate)

        """

        for i, parse_entry in enumerate(parse_packet):

            action = ParseAction(label=self.label,
                    action_index=self.no_of_publications + i,
                    _db=self._db)

            action.new_action(parse_entry=parse_entry)

    def _prepare_run_parameters(self, restart_mode, cleanup, **kwargs):
        """
        Helper method to prepare run arguments for ``self.run_job()``

        Parameters and keyword arguments are the same as in self.run_job()

        Returns
        -------
        run_parameters : dict
            Appropriately sanitized arguments for a parse job

        """

        if restart_mode not in ('from_scratch', 'resume'):
            raise ValueError('scrape_mode must be "from_scratch" or "resume".')

        if not isinstance(cleanup, bool):
            raise ValueError('The "cleanup" parameter must be boolean.')

        kwargs.setdefault('publishers', None)
        kwargs.setdefault('journals', None)
        kwargs.setdefault('data_types', 'txt')

        kwargs.setdefault('no_scrape_mark', False)

        no_scrape_mark = kwargs['no_scrape_mark']

        if not isinstance(no_scrape_mark, bool):
            raise ValueError('The "no_scrape_mark" parameter must be boolean.')

        publishers, journals, data_types =\
                kwargs['publishers'],\
                kwargs['journals'],\
                kwargs['data_types']

        if publishers and not _utils.is_list_of_str(publishers):
            raise TypeError('Invalid "publishers" argument passed to run_job; must be a string or a list of strings.')

        if journals and not _utils.is_list_of_str(journals):
            raise TypeError('Invalid "journals" argument passed to run_job; must be a string or a list of strings.')

        if (data_types and data_types not in ('txt', ['txt'])):
            raise NotImplementedError('Only "txt" data type is currently implemented.')

        run_parameters = {'restart_mode': restart_mode,
                'no_scrape_mark': no_scrape_mark,
                'cleanup': cleanup,
                'publishers': publishers,
                'journals': journals,
                'data_types': data_types,
                }

        return run_parameters

    def run_action(self, action_index=None, _queue=None, **action_parameters):
        """
        Runs the parse action given by ``action_index``

        Parameters
        ----------
        action_index : int
            Index of the parse action to run; defaults to
                ``self.job_step``
        _queue : queue.Queue
            If given, messages will be logged in the job log file

        Keyword Arguments
        -----------------
        publishers : str | list of str | None
            List of candidate parser publisher codes
        journals : str | list of str | None
            List of candidate parser journal codes
        data_types : str | list of str | None
            List of candidate parser data types;
                currently, only 'txt' is supported

        """

        if not action_index:
            action_index = self.job_step

        self._wlog(reports.parse_step_report(self,
            action_index=action_index))

        self.actions[action_index].run(
                _queue=_queue,
                **action_parameters)

        if self.actions[action_index].success == 'F':
            self.job_fails += 1

        if self.actions[action_index].success == 'T':
            self.job_successes += 1

    def _update_scrapes(self):
        """
        Updates the "parsed" status of all scrape jobs/actions corresponding
            to the ``ParseJob``

        The scrape action "parsed" status is updated only if the corresponding
            parse action is successful.

        If the parse action does not correspond to a scrape action
            (parse mode "F"), does nothing.

        If all the successful scrape actions within a scrape job
            are parsed, the scrape job will also be marked as
            completely parsed

        """

        unique_scrape_labels = set(action.scrape_label
            for action in self.actions)

        if unique_scrape_labels != {None}:

            self._wlog(_log.boxed_message('Updating the "parsed" status of scrape jobs/actions'))

            self._wlog('\nReport format:\n<SCRAPE_ACTION_INDEX>: <OLD_PARSED_STATUS> -> <UPDATED_PARSED_STATUS>\n')

            for scrape_label in unique_scrape_labels:

                self._wlog(_log.underlined_message(f'Scrape job: {scrape_label}'))

                scrape_job = ScrapeJob(label=scrape_label, job_mode='write')

                old_job_status = scrape_job.job_parsed

                parse_actions = [action
                        for action in self.successful_actions
                        if action.scrape_label == scrape_label]

                for parse_action in parse_actions:

                    scrape_action = scrape_job.actions\
                            [parse_action.scrape_action_index]

                    old_status = scrape_action.parsed
                    scrape_action.mark_as_parsed()
                    updated_status = scrape_action.parsed

                    self._wlog(f'{scrape_action.action_index}: {old_status} -> {updated_status}')

                scrape_job.update_parsed()
                updated_job_status = scrape_job.job_parsed

                self._wlog(f'\nScrape job {scrape_label} parsed status: {old_job_status} -> {updated_job_status}\n')

            self._wlog(_log.boxed_message('Completed updating the "parsed" status of scrape jobs/actions') + '\n')

        else:
            self._wlog('No scrape jobs were associated with this parse job; no scrape jobs/actions will be labeled as parsed.\n')

    def update_committed(self):
        """
        If all successful actions are committed, mark the job as committed.

        If the job does not exist, does nothing

        """

        if self._job_exists:

            if all(action.committed == 'T'
                    for action in self.successful_actions):
                self.job_committed = 'T'

            else:
                self.job_committed = 'F'

    def unmark_actions(self):
        """
        Set the "committed" status of all parse actions in the job to "F"

        If the job does not exist, does nothing

        """

        if self._job_exists:

            if not self.actions:
                pass

            else:

                for action in self.actions:
                    action.mark_as_uncommitted()

            self.update_committed()
