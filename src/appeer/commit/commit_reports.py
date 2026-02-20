"""Generate appeer commit-related reports"""

from string import ascii_lowercase

import appeer.general.log as _log
import appeer.general.utils as _utils

from appeer.parse.default_metadata import default_metadata


def commit_general_report(job, add_status_info=False):
    """
    Return a formatted report containing general information of a commit job

    Parameters
    ----------
    job : appeer.commit.commit_job.CommitJob
        appeer commit job
    add_status_info : bool
        If True, job status and succ./tot. are added

    Returns
    -------
    report : str
        General information on a commit job

    """

    report = ""

    report += _log.boxed_message(f'COMMIT JOB: {job.label}', centered=True) + '\n'
    report += _log.center(f'Created on {_utils.human_datetime(job.date)}') + '\n'
    report += _log.center(job.description) + '\n\n'

    msg = ''

    msg += f'{"Log":12} {job.log}\n'
    msg += f'{"Mode":12} {job.mode}'

    if add_status_info:
        msg += '\n'
        msg += f'{"Job status":12} {job.job_status}\n'
        msg += f'{"Succ./Tot.":12} {job.job_successes}/{job.no_of_publications}'

    report += _log.boxed_message(msg) + '\n'

    return report

def commit_jobs_summary(commit_table):
    """
    Summary of all commit jobs in the database

    Parameters
    ----------
    commit_table : appeer.db.tables.commit_jobs.CommitJobs
        Instance of CommitJobs table

    Returns
    -------
    report : str
        Summary of all commit jobs

    """

    _msg = f'{"Label":<30} {"Description":<20} {"M":<3} {"S":<3} {"Dup.":<6} {"Pass./Tot.":^10}'

    header_length = len(_msg)
    dashes = header_length * '–'

    report = f'{dashes}\n{_msg}\n{dashes}\n'

    for job in commit_table.entries:

        description = job.description

        if len(description) > 15:
            description = description[0:15] + '...'

        pass_tot = f'{job.job_passes}/{job.no_of_publications}'

        report += f'{job.label:<30} {description:<20} {job.mode:<3} {job.job_status:<3} {job.job_duplicates:<6} {pass_tot:^10}' + '\n'

    report += dashes + '\n'

    report += 'M = Commit mode: (A) Auto; (E) Everything; (P) Parse job' + '\n'
    report += 'S = Job status: (I) Initialized; (R) Running; (X) Executed/Finished; (E) Error' + '\n'
    report += 'Dup. = Number of preexisting DOI entries' + '\n'
    report += 'Pass./Tot. = Ratio of (over)written over total entries' + '\n'

    report += dashes

    return report


def commit_start_report(job, run_parameters):
    """
    Return a formatted report at the beginning of commit job execution

    Parameters
    ----------
    job : appeer.commit.commit_job.CommitJob
        appeer commit job
    run_parameters : dict
        Dictionary containing restart_mode, no_parse_mark, overwrite

    Returns
    -------
    report : str
        Report on the beginning of commit job execution

    """

    current_time = _utils.get_current_datetime()
    human_time = _utils.human_datetime(current_time)

    report = '\n'

    report += _log.boxed_message('COMMIT JOB EXECUTION', centered=True)

    report += '\n'
    report += _log.center(f'{human_time}')
    report += '\n\n'

    msg = ''
    msg += f'{"no_of_publications":<20} {job.no_of_publications}\n'

    for name, value in run_parameters.items():
        msg += f'{name:<20} {value}\n'

    msg = msg.rstrip('\n')

    report += _log.boxed_message(msg, header='Job parameters')

    report += '\n\n'

    if run_parameters['restart_mode'] == 'from_scratch':
        start_resume = 'Starting'

    else:
        start_resume = 'Resuming'

    report += _log.boxed_message(f'{start_resume} commit job from step {job.job_step}/{job.no_of_publications - 1}')

    return report

def commit_step_report(job, action_index=None):
    """
    Return a formatted report at launching of a commit action

    Parameters
    ----------
    job : appeer.commit.commit_job.CommitJob
        appeer commit job
    action_index : int
        Index of the commit action that is beginning;
            defaults to ``job.job_step``

    Returns
    -------
    report : str
        Report on the launch of a commit action

    """

    if not action_index:
        action_index = job.job_step

    current_time = _utils.get_current_datetime()
    human_time = _utils.human_datetime(current_time)

    report = _log.boxed_message(f'Committing entry {job.job_step}/{job.no_of_publications - 1}; {human_time}')

    return report

def commit_action_start(action):
    """
    Return a formatted report at the beginning of a commit action

    Parameters
    ----------
    action : appeer.commit.commit_action.CommitAction
        appeer commit action

    Returns
    -------
    report : str
        Report on the beginning of a commit action

    """

    metadata_list = default_metadata()

    report = '\n' + _log.underlined_message('METADATA SOURCE') + '\n'

    report += f'{"Parse job label":20} {action.parse_label}\n'
    report += f'{"Parse action index":20} {action.parse_action_index}\n\n'

    report += _log.underlined_message('METADATA')
    report += '\n\n'

    align = len(max(metadata_list, key=len)) + 4

    for meta in metadata_list:

        meta_brackets = f'[{meta.upper()}]'

        if meta not in ['author_names', 'affiliations']:
            report += f'{meta_brackets:<{align}} {getattr(action, meta)}\n'

    for meta in ['author_names', 'affiliations']:

        report += f'\n{f"[{meta.upper()}]":<{align}} '

        print(getattr(action,meta))

        meta_values = _utils.aff_str2list(getattr(action, meta))

        if meta_values:

            align = len(str(len(meta_values))) + 3

            report += '\n\n'

            for i, meta_list in enumerate(meta_values):

                if len(meta_list) > 1:
                    suff = ascii_lowercase[:len(meta_list)]

                else:
                    suff = ' '

                for j, m in enumerate(meta_list):

                    meta_string = f'({i+1}{suff[j].strip()})'

                    report += f'{meta_string:<{align}} {m}\n'

        else:
            report += 'None\n'

    return report

def commit_action_end(action):
    """
    Return a formatted report at the end of a commit action

    Parameters
    ----------
    action : appeer.commit.commit_action.CommitAction
        appeer commit action

    Returns
    -------
    report : str
        Report on the beginning of a commit action

    """

    report = _log.underlined_message('DATABASE STATUS UPDATE') + '\n'

    report += f'{"entry":18} {action.doi}\n'
    report += f'{"preexisting":18} {action.duplicate}\n'

    report += f'{"database_action":18} '

    passed = bool(action.passed == 'T')
    duplicate = bool(action.duplicate == 'T')

    if not duplicate and passed:
        report += 'INSERT'

    elif duplicate and passed:
        report += 'REPLACE'

    elif duplicate and not passed:
        report += 'SKIP'

    elif not duplicate and not passed:
        report += 'FAIL'

    report += '\n'

    return report

def commit_end(job):
    """
    Return a formatted report at the end of a commit job

    Parameters
    ----------
    job : appeer.commit.commit_job.CommitJob
        appeer commit job

    Returns
    -------
    report : str
        Report on the end of a commit job

    """

    report = ''

    report += _log.boxed_message('COMMIT JOB EXECUTED', centered=True) + '\n'

    align = len(max('Successes', 'Fails', 'Passed', 'Duplicates', key=len)) + 2

    msg = ''

    msg += f'{"Succeeded":<{align}} {job.job_successes}/{job.no_of_publications}\n'
    msg += f'{"Failed":<{align}} {job.job_fails}/{job.no_of_publications}\n'
    msg += f'{"Duplicates":<{align}} {job.job_duplicates}/{job.no_of_publications}\n'
    msg += f'{"Passed":<{align}} {job.job_passes}/{job.no_of_publications}\n'
    msg += f'{"Skipped":<{align}} {len(job.skipped_actions)}/{job.no_of_publications}\n'

    msg = msg.rstrip('\n')
    report += _log.boxed_message(msg, centered=True)

    report += '\n\n'

    if job.job_fails > 0:

        report += _log.boxed_message('Failed commit actions')
        report += '\n\n'

        report += action_list_summary(action_list=job.failed_actions)

        report += '\n'

    if job.passed_actions:

        report += _log.boxed_message('Inserted/updated entries')
        report += '\n\n'

        report += action_list_summary(action_list=job.passed_actions)

        report += '\n'

    if job.skipped_actions:

        report += _log.boxed_message('Skipped entries')
        report += '\n\n'

        report += action_list_summary(action_list=job.skipped_actions)

        report += '\n'

    return report

def action_list_summary(action_list): #pylint:disable='too-many-locals'
    """
    Return a summary of a list of commit actions

    Parameters
    ----------
    action_list : list of appeer.commit.commit_job.CommitAction
        List of appeer parse actions
    add_parsed_info : bool
        If True, write action.committed values to summary

    Returns
    -------
    report : str
        Summary of a list of actions

    """

    action_indices = [str(action.action_index) for action in action_list]
    dois = [action.doi for action in action_list]
    passed = [action.passed for action in action_list]
    statuses = [action.status for action in action_list]

    max_index_len = max(len(max(action_indices, key=len)), len('Index'))
    max_doi_len = max(len(max(dois, key=len)), len('DOI'))
    max_passed_len = max(len(max(passed, key=len)), len('Passed'))
    max_status_len = max(len(max(statuses, key=len)), len('Status'))

    _msg = f'{"Index":<{max_index_len}}  {"DOI":<{max_doi_len}}  {"Passed":<{max_passed_len}}  {"Status":<{max_status_len}}'

    report = _log.underlined_message(_msg) + '\n'

    for i in range(len(action_list)):
        report += f'{action_indices[i]:<{max_index_len}}  {dois[i]:<{max_doi_len}}    {passed[i]:<{max_passed_len}}  {statuses[i]:<{max_status_len}}'

        report += '\n'

    return report

def end_logo(job):
    """
    Write a logo and the commit job label at the end of the job

    Parameters
    ----------
    job : appeer.commit.commit_job.CommitJob
        appeer commit job

    Returns
    -------
    report : str
        Logo and commit job label for the end of a commit job

    """

    current_time = _utils.get_current_datetime()
    human_time = _utils.human_datetime(current_time)

    report = _log.get_logo(centered=True) + '\n'
    report += _log.boxed_message(f'COMMIT JOB: {job.label}', centered=True) + '\n'
    report += _log.center(f'Finished on {human_time}') + '\n'

    return report
