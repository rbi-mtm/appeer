"""Commit publications to the pub.db database"""

import sys
import queue

from appeer.general import log as _log

from appeer.jobs.job import Job

from appeer.parse.parse_job import ParseJob

from appeer.commit.commit_action import CommitAction
from appeer.commit.commit_packer import CommitPacker
from appeer.commit import commit_reports as reports


class CommitJob(Job, job_type='commit_job'): #pylint:disable=too-many-instance-attributes
    """
    Commit parsed publications

    The ``mode`` attribute defines four available commit modes:

        1) Auto (A) [DEFAULT]
            Commit publications found through the ``parse_jobs`` table,
            for the parse jobs that were executed but not previously
            committed.

            Note that only the parse actions which were not previously
            committed will be committed. Default mode

        2) Everything (E)
            Commit all publications found through the ``parse_jobs`` table,
            regardless of whether the jobs and the corresponding actions were
            previously committed. Only executed jobs are considered

        3) Parse job (P)
            Commit a list of parse jobs with the given labels, regardless of 
            whether the jobs and the corresponding actions were previously
            parsed

    Instances of the CommitJob class have dynamically created properties
        corresponding to the columns of the ``commit_jobs`` table in the
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
    mode : str
        Commit mode; one of ('A', 'E', 'P'); 'A' is default
    job_status : str
        Job status; one of ('I', 'W', 'R', 'E', 'X'); mutable
    job_step : int
        Index of the current job action; mutable
    job_successes : int
        Counts how many actions were succesfully ran; mutable
    job_fails : int
        Counts how many actions failed; mutable
    job_passes : int
        Counts how many actions resulted in (over)writing an entry
            in the ``pub`` table; one of ('T', 'F'); mutable
    job_passes : int
        Counts how many actions contain a DOI already existing
            in the ``pub`` table; one of ('T', 'F'), mutable
    no_of_publications : int
        Counts how many publications were added to the job; mutable

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

    @property
    def passed_actions(self):
        """
        Get executed actions that resulted in a change of "pub.db"

        Returns
        -------
        _passed_actions : list of appeer.commit.commit_action.CommitAction
            List of executed and passed CommitActions

        """

        _passed_actions = [action for action in self.actions
                if action.passed == 'T' and action.success == 'T']

        return _passed_actions

    @property
    def skipped_actions(self):
        """
        Get executed actions that did not result in a change of "pub.db"

        Returns
        -------
        _skipped_actions : list of appeer.commit.commit_action.CommitAction
            List of executed, but not passed commit actions

        """

        _skipped_actions = [action for action in self.actions
                if action.passed == 'F' and action.success == 'T']

        return _skipped_actions

    def _prepare_new_job_parameters(self, **kwargs):
        """
        Set defaults and sanitize parameters passed to ``self.new_job()``

        Keyword Arguments
        -----------------
        description : str
            Optional job description
        log_directory : str
            Directory into which to store the log file
        mode : str
            Commit mode; one of ('A', 'E', 'P'); 'A' is default

        Returns
        -------
        job_arguments : dict
            The inputted keyword arguments with added defaults

        """

        kwargs.setdefault('mode', 'A')

        kwargs.setdefault('description', None)
        kwargs.setdefault('log_directory', None)

        job_parameters = {
                'description': kwargs['description'],
                'log_directory': kwargs['log_directory'],
                'mode': kwargs['mode']
                }

        return job_parameters

    def add_publications(self, data_source=None):
        """
        Add publications to be committed

        Depending on the ``self.mode`` attribute, data_source may be:

            1) (A): None
            2) (E): None
            3) (P): List of parse job labels

        Parameters
        ----------
        data_source : None | list of str
            None for modes ('A', 'E'), list of scrape job labels ('P'),

        """

        if not self._job_exists:
            raise PermissionError('Cannot add publications to a commit job; most likely, the job has not yet been initialized.')

        if self.job_status == 'X':
            raise PermissionError(f'Cannot add new publications to the commit job "{self.label}"; the job has already been executed.')

        if self.job_status == 'R':
            raise PermissionError(f'Cannot add new publications to the commit job "{self.label}"; the job is in the "R" (Running) state.')

        if self.job_status == 'E':
            raise PermissionError(f'Cannot add new publications to the commit job "{self.label}"; the job is in the "E" (Error) state.')

        self._job_mode = 'write'

        self._queue = queue.Queue()
        self._start_log_server()
        try:
            self._prepare_committing(data_source=data_source)
        finally:
            self._stop_log_server()

    def _prepare_committing(self, data_source):
        """
        Prepare inputted data for committing depending on the commit mode

        Parameters
        ----------
        data_source : None | list of str
            None for modes ('A', 'E'), list of parse job labels ('P'),

        """

        self._wlog(_log.boxed_message('PREPARING METADATA', centered=True) + '\n')

        try:

            packer = CommitPacker(commit_mode=self.mode,
                    data_source=data_source,
                    _queue=self._queue)

        except ValueError as err:
            self._wlog(err)

        else:

            packer.pack()

            if packer.success:
                self._queue.put(
                        f'Prepared {len(packer.packet)} entries.')

                self._add_actions(commit_packet=packer.packet)

                self.no_of_publications = len(self.actions)
                self.job_status = 'W'

            else:
                self._queue.put('No new actions were added to the commit job.')

    def _add_actions(self, commit_packet):
        """
        Add CommitActions to the CommitJob

        ``commit_packet`` is given by ``appeer.commit.commit_packer.packet``

        Parameters
        ----------
        commit_packet : list of appeer.commit.commit_packer._CommitEntry
            Packet containing info on the metadata to be committed

        """

        for i, commit_entry in enumerate(commit_packet):

            action = CommitAction(label=self.label,
                    action_index=self.no_of_publications + i,
                    _db=self._db)

            action.new_action(commit_entry=commit_entry)

    def run_job(self, restart_mode='from_scratch', **kwargs):
        """
        Runs the actions defined in self.actions

        If ``restart_mode == 'from_scratch'``, the ``job_step`` is set to 0
            and the parsing is performed for all the actions in the job.

        If ``restart_mode == 'resume'``, parsing is resumed from the current
            ``job_step``.

        If the keyword argument ``no_parse_mark == True``, parse jobs
            and actions corresponding to parse actions will not be labeled
            as committed, even if they are committed successfully.

        Each entry in the ``pub`` table must have a unique ``doi`` value.

            If an entry containing a DOI value already existing in the table
                is attempted to be added to the database, the ``overwrite``
                keyword argument governs the behavior of commit actions:

                (1) If ``overwrite == False``, the entry is not inserted

                (2) If ``overwrite == True``, the entry with the given
                    DOI is updated

        Parameters
        ----------
        restart_mode : str
            Must be in ('from_scratch', 'resume')

        Keyword Arguments
        -----------------
        no_parse_mark : bool
            If True, parse jobs will not be labeled as committed
                even if they are committed successfully
        overwrite : bool
            If False, ignore a duplicate DOI entry (default);
                if True, overwrite a duplicate DOI entry;
                if the given DOI is unique, this parameter has no impact

        """

        if self.no_of_publications == 0:
            self._wlog(f'\nError: Cannot run commit job "{self.label}"; no publications were added to this job. Exiting.\n')
            self.job_status = 'E'
            sys.exit()

        run_parameters =\
                self._prepare_run_parameters(restart_mode=restart_mode,
                        **kwargs)

        self._job_mode = 'write'

        if run_parameters['restart_mode'] == 'from_scratch':

            self.job_step = 0
            self.job_fails = 0
            self.job_successes = 0

        self.job_status = 'R'

        self._wlog(reports.commit_start_report(job=self,
            run_parameters=run_parameters))

        self._queue = queue.Queue()
        self._start_log_server()

        action_parameters = {
                'overwrite': run_parameters['overwrite'],
                }

        try:
            while self.job_step < self.no_of_publications:

                self.run_action(_queue=self._queue,
                        action_index=self.job_step,
                        **action_parameters)

                self.job_step += 1
        finally:
            self._stop_log_server()

        if all(status == 'X' for status in
                (getattr(action, 'status') for action in self.actions)):

            self.job_status = 'X'

        self._wlog(reports.commit_end(job=self))

        if not run_parameters['no_parse_mark']:

            if not self.passed_actions:
                self._wlog('No commit actions resulted in a change of pub.db; no parse job/actions will be marked as committed.\n')

            else:
                self._update_parses()

        else:
            self._wlog('no_parse_mark was set to True; no parse job/actions will be marked as committed.\n')

        self._wlog(reports.end_logo(job=self))

    def _prepare_run_parameters(self, restart_mode, **kwargs):
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

        kwargs.setdefault('no_parse_mark', False)
        no_parse_mark = kwargs['no_parse_mark']

        if not isinstance(no_parse_mark, bool):
            raise ValueError('The "no_parse_mark" parameter must be boolean.')

        kwargs.setdefault('overwrite', False)
        overwrite = kwargs['overwrite']

        if not isinstance(overwrite, bool):
            raise ValueError('The "overwrite" parameter must be boolean.')

        run_parameters = {'restart_mode': restart_mode,
                'no_parse_mark': no_parse_mark,
                'overwrite': overwrite
                }

        return run_parameters

    def run_action(self, action_index=None, _queue=None, **action_parameters):
        """
        Runs the commit action given by ``action_index``

        Parameters
        ----------
        action_index : int
            Index of the commit action to run; defaults to
                ``self.job_step``
        _queue : queue.Queue
            If given, messages will be logged in the job log file

        Keyword Arguments
        -----------------
        overwrite : bool
            If False, ignore a duplicate DOI entry (default);
            if True, overwrite a duplicate DOI entry;
            if the given DOI is unique, this parameter has no impact

        """

        if not action_index:
            action_index = self.job_step

        self._wlog(reports.commit_step_report(self,
            action_index=action_index))

        self.actions[action_index].run(
                _queue=_queue,
                **action_parameters)

        if self.actions[action_index].success == 'F':
            self.job_fails += 1

        if self.actions[action_index].success == 'T':
            self.job_successes += 1

        if self.actions[action_index].passed == 'T':
            self.job_passes += 1

        if self.actions[action_index].duplicate == 'T':
            self.job_duplicates += 1

    def _update_parses(self):
        """
        Updates the "committed" status of all parse jobs/actions corresponding
            to the ``CommitJob``

        The parse action "committed" status is updated only if the
            corresponding parse action is successful AND passed.

        If all the successful parse actions within a parse job
            are committed, the parse job will also be marked as
            completely committed

        """

        unique_parse_labels = set(action.parse_label
            for action in self.actions)

        self._wlog(_log.boxed_message('Updating the "commited" status of parse jobs/actions'))

        self._wlog('\nReport format:\n<PARSE_ACTION_INDEX>: <OLD_COMMITTED_STATUS> -> <UPDATED_COMMITTED_STATUS>\n')

        for parse_label in unique_parse_labels:

            self._wlog(_log.underlined_message(f'Parse job: {parse_label}'))

            parse_job = ParseJob(label=parse_label, job_mode='write')

            old_job_status = parse_job.job_committed

            passed_actions = [action
                    for action in self.passed_actions
                    if action.parse_label == parse_label and\
                            action.success == 'T']

            for passed_action in passed_actions:

                parse_action = parse_job.actions\
                        [passed_action.parse_action_index]

                old_status = parse_action.committed
                parse_action.mark_as_committed()
                updated_status = parse_action.committed

                self._wlog(f'{parse_action.action_index}: {old_status} -> {updated_status}')

            parse_job.update_committed()
            updated_job_status = parse_job.job_committed

            self._wlog(f'\nParse job {parse_label} committed status: {old_job_status} -> {updated_job_status}\n')

        self._wlog(_log.boxed_message('Completed updating the "committed" status of parse jobs/actions') + '\n')
