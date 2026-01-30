"""Defines the ``appeer commit`` CLI"""

import sys

import click

from appeer.commit import commit_scripts

@click.command(help="""*** Commit publications metadata ***

    (*) The most common usage is to find and commit publications metadata automatically:

            appeer commit

    (*) Examples of advanced usage:

            appeer commit -x

            appeer commit -E -s "Commit job description" -o

            appeer commit -P parse_label1 parse_label2

    (*) Commiting can be performed in one of 3 modes, defined by the (-A, -E, -P flags):

        (1) Mode A [DEFAULT]

            Searches the parse jobs database and commits previously uncommitted publications

                appeer commit

        (2) Mode E

            Commits all publications found in the parse jobs database, regardless of whether they were previously committed

                appeer parse -E

        (3) Mode P

            Commits publications from a list of parse job labels

                appeer parse -S parse_label1 parse_label2

    (*) Several other options and flags are available. The most relevant ones are:

        (1) -o flag: By default, entries with DOIs that already exist in the "pub" database are skipped. If this flag is provided, such entries will be updated.

        (2) -x flag: DO NOT mark parse jobs as committed upon commit job completion, even if they were successfully committed


""", short_help='Commit publications metadata')
@click.argument('inputs', nargs=-1)
@click.option('-A', '--automatic', 'mode', flag_value='A', default=True,
        help="Commit mode A [default]")
@click.option('-E', '--everything', 'mode', flag_value='E',
        help='Commit mode E')
@click.option('-P', '--parse_jobs', 'mode', flag_value='P',
        help='Commit mode P')
@click.option('-o', '--overwrite',
        is_flag=True, default=False,
        help="Overwrite existing entries")
@click.option('-x', '--no_parse_mark',
        is_flag=True, default=False,
        help="Do not mark parse jobs as committed")
@click.option('-s', '--description', 'description',
        help="Optional description of the commit job")
@click.option('-l', '--log_directory',
        type=click.Path(file_okay=False, writable=True),
        help="Directory in which to store the log")
@click.option('-j', '--job_label',
        help="Commit job label")
def commit_cli(inputs, **kwargs):
    """
    Commit CLI

    """

    data_source = list(inputs) or None

    if (data_source and kwargs['mode'] in ('A', 'E')):
        click.echo('Error: No inputs should be provided in commit modes "A" and "E".')
        sys.exit()

    if (not data_source and kwargs['mode'] == 'P'):
        click.echo('Error: Parse job labels must be provided in commit mode "P".')
        sys.exit()

    commit_scripts.create_and_run(
            data_source=data_source,
            label=kwargs['job_label'],
            **kwargs)
