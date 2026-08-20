"""Basic scrape job scripts"""

import os
from collections import namedtuple

import click

from appeer.general import utils as _utils

from appeer.db.jobs_db import JobsDB

from appeer.scrape.scrape_job import ScrapeJob
from appeer.scrape.scrape_action import ScrapeAction

def create_new_job(**kwargs):
    """
    Create a new scrape job

    Keyword Arguments
    -----------------
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

    Returns
    -------
    sj : appeer.scrape.scrape_job.ScrapeJob
        Scrape job instance with the label set to the new job label

    """

    sj = ScrapeJob(job_mode='write')
    sj.new_job(**kwargs)

    return sj

def append_publications(label, publications):
    """
    Add ``publications`` to a preexisting job

    Parameters
    ----------
    label : str
        Unique job label
    publications : list | str
        List of URLs or path to a JSON or plaintext file
            containing URLs

    Returns
    -------
    sj : appeer.scrape.scrape_job.ScrapeJob
        Scrape job instance with appeded publications

    """
    sj = ScrapeJob(label=label, job_mode='write')
    sj.add_publications(publications=publications)

    return sj

def run_job(label,
            scrape_mode='from_scratch',
            cleanup=False,
            **kwargs):
    """
    Run the job with the given ``label``

    Parameters
    ----------
    label : str
        Unique job label
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

    sj = ScrapeJob(label=label, job_mode='write')
    sj.run_job(scrape_mode=scrape_mode,
               cleanup=cleanup,
               **kwargs)

def create_and_run(publications,
                   label=None,
                   cleanup=False,
                   **kwargs):
    """
    Create and run a scrape job

    Parameters
    ----------
    publications : list | str
        List of URLs or path to a JSON or plaintext file
            containing URLs
    label : str
        Unique job label
    cleanup : bool
        If True, the final ZIP archive will be kept, while the directory
            containing the downloaded data will be deleted

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

    sj = ScrapeJob(job_mode='write')

    sj.new_job(label=label, **kwargs)

    sj.add_publications(publications)

    sj.run_job(cleanup=cleanup,
               scrape_mode='from_scratch',
               **kwargs)

def get_unparsed_job_labels():
    """
    Returns a list of scrape job labels which are executed and unparsed

    Returns
    -------
    unparsed_job_labels : list of str
        List of scrape job labels which are executed and unparsed

    """

    with JobsDB() as db:
        unparsed_jobs = db.scrape_jobs.unparsed

    unparsed_job_labels = [job.label for job in unparsed_jobs]

    return unparsed_job_labels

def get_executed_job_labels():
    """
    Returns a list of scrape job labels which are executed

    Returns
    -------
    executed_job_labels : list of str
        List of scrape job labels which are executed

    """

    with JobsDB() as db:
        executed_jobs = db.scrape_jobs.executed

    executed_job_labels = [job.label for job in executed_jobs]

    return executed_job_labels

def get_execution_dict(job_labels):
    """
    Get a dictionary describing the status of a list of scrape jobs

    Parameters
    ----------
    job_labels : list of str
        List of scrape job labels

    Returns
    -------
    scrape_jobs_executed_dict : dict
        Dictionary of form {label1: status1, label2: status2, ...},
            where the keys are scrape job labels and the values are
            the job statuses

    """

    if not _utils.is_list_of_str(job_labels):
        raise TypeError('Scrape job labels must be provided as a list of strings or a single string.')

    if isinstance(job_labels, str):
        job_labels = [job_labels]

    try:

        sjs = [ScrapeJob(label=label) for label in job_labels]
        statuses = [sj.job_status if sj.job_status else 'N/A' for sj in sjs]

    # This means that an invalid job label was passed, so iterate the labels
    # one-by-one to find the error. This edge case is written as a seperate
    # block because it's slower to iterate instead of using list comprehension.
    except ValueError:

        statuses = []

        for label in job_labels:

            try:

                sj = ScrapeJob(label=label)

                if sj.job_status:
                    statuses.append(sj.job_status)

                else:
                    statuses.append('N/A')

            except ValueError:
                statuses.append('N/A')

    scrape_jobs_executed_dict = dict(zip(job_labels, statuses))

    return scrape_jobs_executed_dict

def check_action_outputs(actions):
    """
    Get a named tuple describing whether scraped files are readable and exist

    Used by ParsePacker to determine which files can be read directly. If the
        files are not directly accessible, the corresponding scrape job ZIP
        files will be marked for extraction.

    If a nonexistent action is passed, a ValueError is raised.

    Parameters
    ----------
    actions : list of appeer.scrape.scrape_action.ScrapeAction
        List of scrape actions

    Returns
    -------
    actions_files : list of _ScrapeActionFile
        List of named tuples with the information necessary for ParsePacker

    """

    _ScrapeActionFile = namedtuple('_ScrapeActionFile',
        ['label',
        'action_index',
        'out_file',
        'file_ok'])

    check_list_of_actions = True

    if not (actions and isinstance(actions, (list, ScrapeAction))):
        check_list_of_actions = False

    if isinstance(actions, list):
        if not all(s and isinstance(s, ScrapeAction) for s in actions):
            check_list_of_actions = False

    if not check_list_of_actions:
        raise ValueError('Actions must be provided as a list of ScrapeAction instances.')

    if isinstance(actions, ScrapeAction):
        actions = [actions]

    actions_files = []

    # Probably faster with comprehension,
    # but iterate explicitly for readability
    for action in actions:

        if not action._action_exists: #pylint:disable=protected-access
            raise ValueError('Nonexistent action passed to check_action_outputs.')

        f = _utils.abspath(action.out_file)

        file_readable = os.access(f, os.R_OK)

        actions_files.append(_ScrapeActionFile(
            label=action.label,
            action_index=action.action_index,
            out_file=f,
            file_ok=file_readable))

    return actions_files

def unmark_scrapes(scrape_labels=None, _all=False):
    """
    Set the "parsed" status of all scrape actions in ``scrape_jobs`` to "F"

    If ``_all is True``, mark ALL scrape jobs as unparsed.

    ``scrape_labels`` and ``_all`` cannot be simultaneously be truthy.

    Parameters
    ----------
    scrape_labels : None | list of str
        List of appeer scrape job labels
     _all : bool
        If True, mark ALL scrape jobs as unparsed

    """

    if scrape_labels and _all:
        click.echo('Cannot simultaneously provide "scrape_labels" and "_all" parameters.')
        return

    if _all:

        jobs_db = JobsDB()
        scrape_labels = [entry.label
                for entry in jobs_db.scrape_jobs.entries]

    if not _utils.is_list_of_str(scrape_labels):
        click.echo('Scrape labels must be provided as a list of strings.')
        return

    for scrape_label in scrape_labels:

        sj = ScrapeJob(scrape_label, job_mode='write')

        if not sj._job_exists: #pylint:disable=protected-access
            click.echo(f'Scrape job "{scrape_label}" does not exist.')

        else:

            job_old_status = sj.job_parsed

            if not sj.actions:
                click.echo(f'No actions associated with scrape job "{scrape_label}"')

            sj.unmark_actions()

            job_new_status = sj.job_parsed

            click.echo(f'Scrape job "{scrape_label}": Parsed status updated {job_old_status} -> {job_new_status}')
