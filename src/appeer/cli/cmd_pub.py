"""Defines the ``appeer pub`` CLI"""

import traceback

import click

from appeer.pub import status
from appeer.pub.researcher import PubReSearcher

@click.group('pub', invoke_without_command=True,
        help="""*** Analyze publications ***

        (*) Simple alphabetical list of publishers:

                appeer pub -P

        (*) Simple alphabetical list of journals for a given publisher:

                appeer pub -J -p 'Nature Porfolio'

        (*) A semi-detailed summary of a given publisher:

                appeer pub -p 'Nature Portfolio'

        (*) A semi-detailed summary of a given (publisher, journal) pair:

                appeer pub -p 'Nature Portfolio' -j 'Nature'

""", short_help='Analyze publications')
@click.option('-P', '--publisher_list', is_flag=True, default=False)
@click.option('-J', '--journal_list', is_flag=True, default=False)
@click.option('-p', '--publisher')
@click.option('-j', '--journal')
@click.pass_context
def pub_cli(ctx, **kwargs):
    """
    Pub CLI

    """

    if ctx.invoked_subcommand is None:

        if kwargs['publisher_list']:
            click.echo(status.unique_publishers_report())

        elif kwargs['journal_list']:

            if not kwargs['publisher']:
                click.echo('A publisher must be provided, e.g. appeer pub -J -p "Nature Portfolio"')

            else:
                click.echo(status.unique_journals_report(
                    publisher=kwargs['publisher']))

        elif kwargs['publisher'] and not kwargs['journal']:
            click.echo(status.publisher_summary_report(
                publisher=kwargs['publisher']))

        elif kwargs['journal']:

            if not kwargs['publisher']:
                click.echo('A publisher must be provided, e.g. appeer pub -p "Nature Portfolio" -j "Nature"')

            else:

                click.echo(status.journal_summary_report(
                    publisher=kwargs['publisher'],
                    journal=kwargs['journal']))

        else:
            ctx = click.get_current_context()
            click.echo(ctx.get_help())
            ctx.exit()


@click.command('search',
        help="""*** Search through the publications database ***

        Publications may be filtered using any combination of the following criteria:

            (1) List of publishers

                appeer pub search -N 'Nature Portfolio' -N 'The Royal Society of Chemistry'

            (2) List of journals

                appeer pub search -J 'Nature' -J 'Nature Communications'

            (3) List of publication types (WARNING: experimental feature)

                appeer pub search -T 'Article' -T 'Paper'

            (4) Minimum/maximum received/published/accepted dates

                appeer pub search -r '1995' -R '2000-03' -A '2000-05-01'

                Valid date formats: (a) YYYY (b) YYYY-MM (c) YYYY-MM-DD

        (*) If no filters are passed, all entries in the database are returned

        (*) By default, titles, publication types,
        numbers of authors and affiliations are NOT returned.
        To return them, pass the appropriate flag:

                appeer pub search -r '2000' --get_title --get_author

        (*) The results of the search may be saved to a JSON file:

                appeer pub search -r '2000' -o 'my_search.json'

        (*) Invoking the command without the -o option will print a summary of the search

               """, short_help='Search through the publications database')
@click.option('--publisher', '-N', multiple=True, help='Normalized publisher name')
@click.option('--journal', '-J', multiple=True, help='Normalized journal name')
@click.option('--publication_type', '-T', multiple=True, help='Publication type')
@click.option('--min_received', '-r', help='Earliest received date')
@click.option('--max_received', '-R', help='Latest received date')
@click.option('--min_accepted', '-a', help='Earliest accepted date')
@click.option('--max_accepted', '-A', help='Latest accepted date')
@click.option('--min_published', '-p', help='Earliest published date')
@click.option('--max_published', '-P', help='Latest published date')
@click.option('--output', '-o', help='Name of output JSON file',
              type=click.Path(dir_okay=False, writable=True))
@click.option('--get_title', is_flag=True, default=False, help='Include publication titles in the results')
@click.option('--get_publication_type', is_flag=True, default=False, help='Include publication types in the results')
@click.option('--get_no_of_authors', is_flag=True, default=False, help='Include number of authors in the results')
@click.option('--get_affiliations', is_flag=True, default=False, help='Include affiliations in the results')

def pub_search_cli(**kwargs):
    """Pub search CLI"""

    clean_dict = {}

    for key, value in kwargs.items():

        if value:

            if key in ('publisher', 'journal'):
                clean_dict[f'normalized_{key}'] = list(value)

            elif key == 'publication_type':
                clean_dict[key] = list(value)

            elif key in ('min_received', 'max_received',
                         'min_accepted', 'max_accepted',
                         'min_published', 'max_published'
                         ):
                clean_dict[key] = value

        else:
            pass

    researcher = PubReSearcher()

    try:

        researcher.search_pub(
                get_title=kwargs['get_title'],
                get_publication_type=kwargs['get_publication_type'],
                get_no_of_authors=kwargs['get_no_of_authors'],
                get_affiliations=kwargs['get_affiliations'],
                **clean_dict)

        click.echo(researcher.search_summary)

    except ValueError as exc:
        click.echo(f'Search failed. Most likely, an invalid filter was passed. Possible cause: {exc.__cause__}')

pub_cli.add_command(pub_search_cli)
