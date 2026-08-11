"""Scrape publications for later parsing"""

import sys
import os
import time
import threading
import queue

from appeer.general.datadir import Datadir
from appeer.general.config import Config
from appeer.general.utils import\
    archive_list_of_files, delete_directory, abspath

from appeer.jobs.job import Job
from appeer.scrape import scrape_reports as reports

from appeer.scrape.input_handling import\
        parse_data_source, handle_input_reading

from appeer.scrape.scrape_action import ScrapeAction
from appeer.scrape.strategies.scrape_plan import ScrapePlan


class ScrapeJob(Job, job_type='scrape_job'): #pylint:disable=too-many-instance-attributes
    """
    Scrape publications for later parsing

    Instances of the ScrapeJob class have dynamically created properties
        corresponding to the columns of the ``scrape_jobs`` table in the
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
    download_directory : str
        Directory into which to download the data
    zip_file : str
        Path to the output ZIP file
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
    job_parsed : str
        Whether all scraped data corresponding to the job is parsed;
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

    @property
    def summary(self):
        """
        A formatted summary of the scrape job

        Returns
        -------
        _summary : str
            Job summary

        """

        if not self._job_exists:
            _summary = f'Scrape job {self.label} does not exist.'

        else:
            _summary = reports.scrape_job_summary(job=self)

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
        download_directory : str
            Directory into which to download the data
        zip_file : str
            Path to the output ZIP file

        Returns
        -------
        job_arguments : dict
            The inputted keyword arguments with added defaults

        """

        datadir = Datadir()

        default_download_directory = os.path.join(datadir.downloads,
                self.label)
        kwargs.setdefault('download_directory', default_download_directory)

        if kwargs['download_directory'] is None:
            kwargs['download_directory'] = default_download_directory

        kwargs['download_directory'] = abspath(
                kwargs['download_directory'])

        default_zip_file = os.path.join(datadir.scrape_archives,
                f'{self.label}.zip')

        kwargs.setdefault('zip_file', default_zip_file)

        if kwargs['zip_file'] is None:
            kwargs['zip_file'] = default_zip_file

        if not kwargs['zip_file'].endswith('.zip'):
            kwargs['zip_file'] += '.zip'

        kwargs['zip_file'] = abspath(
                kwargs['zip_file'])

        kwargs.setdefault('description', None)
        kwargs.setdefault('log_directory', None)

        job_parameters = {
                'description': kwargs['description'],
                'download_directory': kwargs['download_directory'],
                'zip_file': kwargs['zip_file'],
                'log_directory': kwargs['log_directory']
                }

        return job_parameters

    def add_publications(self, publications):
        """
        Add publications to be scraped

        ``publications`` can be a list of URLs or a string (path to a file)

        In the case a filepath is provided, the file can be either a JSON file 
            (e.g. ``PoP.json`` file containing ``['article_url']`` keys)
            or a plaintext file with each URL in a new line

        Parameters
        ----------
        publications : list | str
            List of URLs or a path to a JSON or plaintext file
                containing URLs

        """

        if not self._job_exists:
            raise PermissionError('Cannot add publications to a scrape job; most likely, the job has not yet been initialized.')

        if self.job_status == 'X':
            raise PermissionError(f'Cannot add new publications to the scrape job "{self.label}"; the job has already been executed.')

        if self.job_status == 'R':
            raise PermissionError(f'Cannot add new publications to the scrape job "{self.label}"; the job is in the "R" (Running) state.')

        if self.job_status == 'E':
            raise PermissionError(f'Cannot add new publications to the scrape job "{self.label}"; the job is in the "E" (Error) state.')

        self._job_mode = 'write'

        data_source, data_source_type,\
                plaintext_ex_message,\
                json_ex_message = parse_data_source(publications)

        reading_passed, reading_report = handle_input_reading(publications,
                data_source_type,
                str(plaintext_ex_message),
                str(json_ex_message))

        self._wlog(reading_report)

        if reading_passed:

            plan = ScrapePlan(data_source)
            self._wlog(reports.scrape_strategy_report(plan=plan,
                offset=self.no_of_publications))

            self._add_actions(plan=plan)

            self.no_of_publications = len(self.actions)
            self.job_status = 'W'

    def _add_actions(self, plan):
        """
        Prepares ScrapeActions according to the given ScrapePlan

        Parameters
        ----------
        plan : appeer.scrape.strategies.scrape_plan.ScrapePlan
            The ScrapePlan containing scrape strategies

        """

        for i, plan_entry in enumerate(plan.strategies.values()):

            action = ScrapeAction(label=self.label,
                    action_index=self.no_of_publications + i)

            action.new_action(plan_entry=plan_entry)

    def run_job(self, scrape_mode='from_scratch', cleanup=False, **kwargs):
        """
        Runs the actions defined in self.actions

        If ``scrape_mode=='from_scratch'``, the ``job_step`` is set to 0 and
            the scraping is performed for all the actions in the job

        If ``scrape_mode=='resume'``, scraping is resumed from the current
            ``job_step``

        At the end of the scrape job, a ZIP archive containing the
            downloaded data will be made
            To delete the downloaded data itself, set ``cleanup==True``

        Several options may be passed as keyword arguments (see below)
            If not given, defaults will be read from the ``appeer``
            configuration file

        Parameters
        ----------
        scrape_mode : str
            Must be in ('from_scratch', 'resume')
        cleanup : bool
            If True, the final ZIP archive will be kept, while the directory
                containing the downloaded data will be deleted

        Keyword Arguments
        -----------------
        sleep_time : float
            Time (in seconds) between sending requests
        max_tries : int
            Maximum number of tries to get a response from an URL before
                giving up
        retry_sleep_time : float
            Time (in seconds) to wait before trying a nonresponsive URL again
        _429_sleep_time : float
            Time (in minutes) to wait if received a 429 status code

        """

        if self.no_of_publications == 0:
            self._wlog(f'\nError: Cannot run scrape job "{self.label}"; no publications were added to this job. Exiting.\n')
            self.job_status = 'E'
            sys.exit()

        run_parameters =\
                self.__prepare_run_parameters(scrape_mode=scrape_mode,
                        cleanup=cleanup,
                        **kwargs)

        self._job_mode = 'write'

        if run_parameters['scrape_mode'] == 'from_scratch':

            self.job_step = 0
            self.job_fails = 0
            self.job_successes = 0

        self.job_status = 'R'

        self._wlog(reports.scrape_start_report(job=self,
            run_parameters=run_parameters))

        self._queue = queue.Queue()
        threading.Thread(target=self._log_server, daemon=True).start()

        action_parameters = {
                'max_tries': run_parameters['max_tries'],
                'retry_sleep_time': run_parameters['retry_sleep_time'],
                '_429_sleep_time': run_parameters['_429_sleep_time']
                }

        while self.job_step < self.no_of_publications:

            self.run_action(_queue=self._queue,
                    action_index=self.job_step,
                    **action_parameters)

            self.job_step += 1

            time.sleep(run_parameters['sleep_time'])

        self._queue.join()

        if all(status == 'X' for status in
                (getattr(action, 'status') for action in self.actions)):

            self.job_status = 'X'

        self._wlog(reports.scrape_end(self))

        if self.successful_actions:
            self._zip_successful()

        if cleanup:
            delete_directory(self.download_directory, verbose=False)
            self._wlog(f'Cleanup requested; deleted {self.download_directory}')

        else:
            self._wlog(f'Cleanup not requested; keeping {self.download_directory}')

        self._wlog(reports.end_logo(self))

    def __prepare_run_parameters(self, scrape_mode, cleanup, **kwargs):
        """
        Helper method to prepare run arguments for ``self.run_job()``

        Parameters and keyword arguments are the same as in self.run_job()

        """

        if scrape_mode not in ('from_scratch', 'resume'):
            raise ValueError('scrape_mode must be "from_scratch" or "resume".')

        if not isinstance(cleanup, bool):
            raise ValueError("The ``cleanup`` parameter must be boolean.")

        scrape_defaults = Config().settings['ScrapeDefaults']

        kwargs.setdefault('sleep_time',
                float(scrape_defaults['sleep_time']))
        kwargs.setdefault('max_tries',
                int(scrape_defaults['max_tries']))
        kwargs.setdefault('retry_sleep_time',
                float(scrape_defaults['retry_sleep_time']))
        kwargs.setdefault('429_sleep_time',
                float(scrape_defaults['429_sleep_time']))

        sleep_time, max_tries, retry_sleep_time, _429_sleep_time =\
                kwargs['sleep_time'], kwargs['max_tries'],\
                kwargs['retry_sleep_time'], kwargs['429_sleep_time']

        if not sleep_time > 0.0:
            raise ValueError('"sleep_time" must be positive.')

        if not isinstance(max_tries, int):
            raise ValueError('"max_tries" must be an integer.')

        if not max_tries >= 0:
            raise ValueError('"max_tries" must be a non-negative integer.')

        if not retry_sleep_time > 0.0:
            raise ValueError('"retry_sleep_time" must be positive.')

        if not _429_sleep_time > 0.0:
            raise ValueError('"_429_sleep_time" must be positive.')

        run_parameters = {'scrape_mode': scrape_mode,
                'cleanup': cleanup,
                'sleep_time': sleep_time,
                'max_tries': max_tries,
                'retry_sleep_time': retry_sleep_time,
                '_429_sleep_time': _429_sleep_time
                }

        return run_parameters

    def run_action(self, action_index=None, _queue=None, **action_parameters):
        """
        Runs the scrape action given by ``action_index``

        Parameters
        ----------
        action_index : int
            Index of the scrape action to be run; defaults to
                ``self.job_step``
        _queue : queue.Queue
            If given, messages will be logged in the job log file

        Keyword Arguments
        -----------------
        max_tries : int
            Maximum number of tries to get a response from an URL before
                giving up
        retry_sleep_time : float
            Time (in seconds) to wait before trying a nonresponsive URL again

        """

        if not action_index:
            action_index = self.job_step

        self._wlog(reports.scrape_step_report(self,
            action_index=action_index))

        self.actions[action_index].run(
                download_directory=self.download_directory,
                _queue=_queue,
                **action_parameters)

        if self.actions[action_index].success == 'F':
            self.job_fails += 1

        if self.actions[action_index].success == 'T':
            self.job_successes += 1

    def _zip_successful(self):
        """
        Zips the output files of successful ScrapeActions

        """

        file_list = [action.out_file for action in self.successful_actions]

        archive_list_of_files(output_filename=self.zip_file,
                file_list=file_list)

        self._wlog(f'Archived {len(self.successful_actions)} publications to {self.zip_file}')

    def update_parsed(self):
        """
        If all successful actions are parsed, mark the job as parsed.

        If the job does not exist, does nothing

        """

        if self._job_exists:

            if all(action.parsed == 'T' for action in self.successful_actions):
                self.job_parsed = 'T'

            else:
                self.job_parsed = 'F'

    def unmark_actions(self):
        """
        Set the "parsed" status of all scrape actions in the job to "F"

        If the job does not exist, does nothing

        """

        if self._job_exists:

            if not self.actions:
                pass

            else:

                for action in self.actions:
                    action.mark_as_unparsed()

            self.update_parsed()
