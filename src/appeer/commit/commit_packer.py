"""Prepare parsed data for committing"""

from collections import namedtuple

import click

from appeer.general import utils as _utils

from appeer.parse.parse_job import ParseJob
from appeer.parse import parse_scripts
from appeer.parse import parse_reports
from appeer.parse.default_metadata import default_metadata
from appeer.parse.metadata import PROVENANCE_FIELDS

_CommitEntry = namedtuple('_CommitEntry', [
    'parse_label',
    'parse_action_index',
    'metadata'
    ])

class CommitPacker:
    """
    Prepare parsed data for committing

    Used by CommitJob to check the validity of the inputted data
        and prepare the data in a unified format

    """

    def __init__(self, commit_mode, data_source, _queue=None):
        """
        Checks if the ``parse_mode`` and ``data_source`` are in valid format

        Parameters
        ----------
        commit_mode : str
            Commit mode; one of ('A', 'E', 'P')
        data_source : None | list of str
            None for commit modes ('A', 'E'),
                list of parse job labels ('P'),
        _queue : queue.Queue
            If given, messages will be logged in the job log file

        """

        self.success = False
        self._queue = _queue

        match commit_mode:

            case 'A' | 'E':
                if data_source is not None:
                    raise ValueError(f'Failed to initialize CommitPacker; the data_source must be None in commit_mode="{commit_mode}".\n')

            case 'P':
                if not _utils.is_list_of_str(data_source):
                    raise ValueError(f'Failed to initialize CommitPacker; in commit_mode="{commit_mode}", the data_source must be provided as a list of strings or a single string."\n')

            case _:
                raise ValueError(f'Failed to initialize CommitPacker; invalid commit_mode={commit_mode} inputted.\n')

        self._commit_mode = commit_mode
        self._data_source = data_source

        self.packet = []

        self._metadata_list = default_metadata() + list(PROVENANCE_FIELDS)

    def pack(self):
        """
        Runs the appropriate packing method depending on the commit mode

        """

        match self._commit_mode:

            case 'A':
                self._pack_mode_A()

            case 'E':
                self._pack_mode_E()

            case 'P':
                self._pack_mode_P()

    def _pack_mode_A(self):
        """
        Prepares a commit packet automatically from uncommited parse jobs

        ``self._data_source`` will be automatically set.

        The packet is prepared only for jobs in the executed ('X') status
            and only previously uncommitted actions are taken into account

        """

        self._cprint('Searching for uncommitted parse jobs...')

        uncommitted_job_labels = parse_scripts.get_uncommitted_job_labels()

        if uncommitted_job_labels:

            self._cprint(f'Found {len(uncommitted_job_labels)} jobs.')
            self._cprint('Preparing the data for committing...')
            self._data_source = uncommitted_job_labels

            self._pack_mode_P()

        else:
            self._cprint('No uncommitted jobs found.')

    def _pack_mode_E(self):
        """
        Prepares a parse packet automatically from executed parse jobs

        ``self._data_source`` will be automatically set.

        The packet is prepared only for jobs in the executed ('X') status.

        In mode 'E', all succesful actions are taken into account,
            regardless of whether they were previously committed.

        """

        self._cprint('Searching for executed parse jobs...')

        executed_job_labels = parse_scripts.get_executed_job_labels()

        if executed_job_labels:

            self._cprint(f'Found {len(executed_job_labels)} jobs.')
            self._cprint('Preparing the data for committing...')
            self._data_source = executed_job_labels

            self._pack_mode_P()

        else:
            self._cprint('No executed jobs found.')

    def _pack_mode_P(self):
        """
        Prepares a parse packet from a list of parse job labels

        ``self._data_source`` must be a list of strings or a single string.

        The packet is prepared only for jobs in the executed ('X') status.

        For those jobs, ``self._prepare_metadata`` is invoked
            to search for successful actions and obtain the
            parsed metadata

        """

        parse_labels = self._data_source

        if isinstance(parse_labels, str):
            parse_labels = [parse_labels]

        no_of_jobs = len(parse_labels)

        self._cprint(f'\nInputted {no_of_jobs} parse job label(s).')
        self._cprint('Checking if the jobs exist and if their status is executed (X)...\n')

        parse_jobs_execution_dict = parse_scripts.get_execution_dict(
                job_labels=parse_labels)

        self._cprint(parse_reports.parse_jobs_execution_report(
            parse_jobs_execution_dict=parse_jobs_execution_dict))

        valid_jobs = [job for job, execution_status in
                parse_jobs_execution_dict.items()
                if execution_status == 'X']

        if valid_jobs:

            self._cprint(f'Determined that {len(valid_jobs)}/{no_of_jobs} inputted parse jobs are executed.\n')

            self._prepare_parsed_metadata(parse_labels=valid_jobs)

        else:
            self._cprint('None of the inputted parse jobs exist or are executed.\n')

    def _prepare_parsed_metadata(self, parse_labels):
        """
        Prepare the parsed metadata from jobs given by ``parse_labels``

        The parsed metadata is obtained from the successful actions
            corresponding to the parse jobs.

        In commit mode 'A', if a parse action was already committed,
            it is ignored.
        In modes 'E' and 'P', all parse actions will be considered
            regardless if they were previously parsed.

        This method should *never* be invoked directly, but only through the
            ``self._pack_*`` methods.

        If a parse job with an execution status other than 'X' is passed
            in ``scrape_labels``, an error is raised

        Parameters
        ----------
        parse_labels : list of str
            List of parse job labels

        """

        match self._commit_mode:

            case 'A':
                ignore_committed_actions = True

            case 'E' | 'P':
                ignore_committed_actions = False

            case _:
                raise ValueError('CommitPacker failed; _prepare_parsed_metadata was invoked in invalid commit mode.')

        relevant_actions = []

        if ignore_committed_actions:
            self._cprint('Searching for successful and uncomitted parse actions...')

        else:
            self._cprint('Searching for successful parse actions...')

        for parse_label in parse_labels:

            parse_job = ParseJob(label=parse_label)

            if not parse_job._job_exists: #pylint:disable=protected-access
                raise ValueError('CommitPacker failed; nonexistent parse job inputted.')
            if not parse_job.job_status == 'X':
                raise ValueError('CommitPacker failed; inputted a parse job which was not executed to _prepare_parsed_metadata.')

            successful_actions = parse_job.successful_actions

            if successful_actions and ignore_committed_actions:

                relevant_actions.extend(
                        [action for action in successful_actions
                        if action.committed == 'F'])

            else:
                relevant_actions.extend(successful_actions)

        if relevant_actions:

            no_of_publications = len(relevant_actions)
            self._cprint(f'Found {no_of_publications} successful parse actions.\n')

            self.packet.extend([_CommitEntry(
                parse_label=action.label,
                parse_action_index=action.action_index,
                metadata={meta: getattr(action, meta)
                    for meta in self._metadata_list
                    })
                for action in relevant_actions
                ])

            self.success = True

        else:
            self._cprint('No valid actions were found.')

    def _cprint(self, message):
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
