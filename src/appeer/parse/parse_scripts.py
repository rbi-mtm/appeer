"""Basic parse job scripts"""

import click

from appeer.general import utils as _utils

from appeer.db.jobs_db import JobsDB

from appeer.parse.parse_job import ParseJob

def create_new_job(**kwargs):
    """
    Create a new parse job

    Keyword Arguments
    -----------------
    label : str
        Unique job label
    description : str
        Optional job description
    log_directory : str
        Directory into which to store the log file
    parse_directory : str
        Directory into which to (temporarily) create files for parsing
    mode : str
        Parsing mode; one of ('A', 'E', 'S', F); 'A' is default
 
    Returns
    -------
    pj : appeer.parse.parse_job.ParseJob
        Parse job instance with the label set to the new job label

    """

    pj = ParseJob(job_mode='write')
    pj.new_job(**kwargs)

    return pj

def run_job(label,
            restart_mode='from_scratch',
            cleanup=False,
            **kwargs):
    """
    Run the parse job with the given ``label``

    Parameters
    ----------
    label : str
        Unique job label
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

    pj = ParseJob(label=label, job_mode='write')
    pj.run_job(restart_mode=restart_mode,
               cleanup=cleanup,
               **kwargs)

def append_publications(label, data_source):
    """
    Add ``publications`` to a preexisting job

    Parameters
    ----------
    label : str
        Unique job label
    data_source : None | list of str
        None for modes ('A', 'E'), list of scrape job labels ('S'),
            list of file paths ('F')

    Returns
    -------
    pj : appeer.parse.parse_job.ParseJob
        Parse job instance with added publications

    """

    pj = ParseJob(label=label, job_mode='write')
    pj.add_publications(data_source=data_source)

    return pj

def create_and_run(data_source,
        label=None, cleanup=False,
        **kwargs):
    """
    Create and run a parse job

    For more details on the parameters, see documentation of ParseJob

    Parameters
    ----------
    data_source : None | list of str
        None for modes ('A', 'E'),
            list of scrape job labels ('S'),
            list of file paths ('F')
    label : str
        Unique job label
    cleanup : bool
        If True, the temporary parse directory will be deleted at the
            end of the parse job

    Keyword Arguments
    -----------------
    description : str
        Optional job description
    log_directory : str
        Directory into which to store the log file
    parse_directory : str
        Directory into which to (temporarily) create files for parsing
    mode : str
        Parsing mode; one of ('A', 'E', 'S', F); 'A' is default
    publishers : str | list of str | None
        List of candidate parser publisher codes
    journals : str | list of str | None
        List of candidate parser journal codes
    data_types : str | list of str | None
        List of candidate parser data types;
            currently, only 'txt' is supported
    no_scrape_mark : bool
        If True, scrape jobs will not be labeled as parsed
            even if they are parsed successfully

    """

    pj = ParseJob(job_mode='write')

    pj.new_job(label=label, **kwargs)

    pj.add_publications(data_source=data_source)

    pj.run_job(restart_mode='from_scratch',
            cleanup=cleanup,
            **kwargs)

def get_uncommitted_job_labels():
    """
    Returns a list of parse job labels which are executed and not committed

    Returns
    -------
    uncommitted_job_labels : list of str
        List of parse job labels which are executed and not committed

    """

    with JobsDB() as db:
        uncommitted_jobs = db.parse_jobs.uncommitted

    uncommitted_job_labels = [job.label for job in uncommitted_jobs]

    return uncommitted_job_labels

def get_executed_job_labels():
    """
    Returns a list of parse job labels which are executed

    Returns
    -------
    executed_job_labels : list of str
        List of parse job labels which are executed

    """

    with JobsDB() as db:
        executed_jobs = db.parse_jobs.executed

    executed_job_labels = [job.label for job in executed_jobs]

    return executed_job_labels

def get_execution_dict(job_labels):
    """
    Get a dictionary describing the status of a list of parse jobs

    Parameters
    ----------
    job_labels : list of str
        List of parse job labels

    Returns
    -------
    parse_jobs_executed_dict : dict
        Dictionary of form {label1: status1, label2: status2, ...},
            where the keys are parse job labels and the values are
            the job statuses

    """

    if not _utils.is_list_of_str(job_labels):
        raise TypeError('Scrape job labels must be provided as a list of strings or a single string.')

    if isinstance(job_labels, str):
        job_labels = [job_labels]

    try:

        pjs = [ParseJob(label=label) for label in job_labels]
        statuses = [pj.job_status if pj.job_status else 'N/A' for pj in pjs]

    # This means that an invalid job label was passed, so iterate the labels
    # one-by-one to find the error. This edge case is written as a seperate
    # block because it's slower to iterate instead of using list comprehension.
    except ValueError:

        statuses = []

        for label in job_labels:

            try:

                pj = ParseJob(label=label)

                if pj.job_status:
                    statuses.append(pj.job_status)

                else:
                    statuses.append('N/A')

            except ValueError:
                statuses.append('N/A')

    parse_jobs_executed_dict = dict(zip(job_labels, statuses))

    return parse_jobs_executed_dict

def unmark_parses(parse_labels=None, _all=False):
    """
    Set the "committed" status of all parse actions in ``parse_jobs`` to "F"

    If ``_all is True``, mark ALL parse jobs as unparsed.

    ``parse_labels`` and ``_all`` cannot be simultaneously be truthy.

    Parameters
    ----------
    parse_labels : None | list of str
        List of appeer parse job labels
     _all : bool
        If True, mark ALL parse jobs as unparsed

    """

    if parse_labels and _all:
        click.echo('Cannot simultaneously provide "parse_labels" and "_all" parameters.')
        return

    if _all:

        jobs_db = JobsDB()
        parse_labels = [entry.label
                for entry in jobs_db.parse_jobs.entries]

    if not _utils.is_list_of_str(parse_labels):
        click.echo('Parse labels must be provided as a list of strings.')
        return

    for parse_label in parse_labels:

        pj = ParseJob(parse_label, job_mode='write')

        if not pj._job_exists: #pylint:disable=protected-access
            click.echo(f'Parse job "{parse_label}" does not exist.')

        else:

            job_old_status = pj.job_committed

            if not pj.actions:
                click.echo(f'No actions associated with scrape job "{parse_label}"')

            pj.unmark_actions()

            job_new_status = pj.job_committed

            click.echo(f'Parse job "{parse_label}": committed status updated {job_old_status} -> {job_new_status}')
