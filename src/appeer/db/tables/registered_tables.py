"""Defines the allowed table names and columns for SQL query sanitization"""

def get_registered_tables():
    """
    Defines the allowed table names and columns for SQL query sanitization

    Returns
    -------
    registered_tables : dict
        Dictionary of allowed table names and the corresponding columns

    """

    registered_tables = {

            'scrape_jobs':
                ['label',
                'date',
                'description',
                'log',
                'download_directory',
                'zip_file',
                'job_status',
                'job_step',
                'job_successes',
                'job_fails',
                'no_of_publications',
                'job_parsed'],

            'scrapes':
                ['label',
                 'action_index',
                 'date',
                 'url',
                 'journal',
                 'strategy',
                 'method',
                 'success',
                 'status',
                 'out_file',
                 'parsed'],

            'parse_jobs':
                ['label',
                 'date',
                 'description',
                 'log',
                 'parse_directory',
                 'mode',
                 'job_status',
                 'job_step',
                 'job_successes',
                 'job_fails',
                 'no_of_publications',
                 'job_committed'],

            'parses':
                ['label',
                 'action_index',
                 'scrape_label',
                 'scrape_action_index',
                 'date',
                 'input_file',
                 'doi',
                 'publisher',
                 'journal',
                 'title',
                 'publication_type',
                 'no_of_authors',
                 'author_names',
                 'affiliations',
                 'received',
                 'accepted',
                 'published',
                 'normalized_received',
                 'normalized_accepted',
                 'normalized_published',
                 'normalized_publisher',
                 'normalized_journal',
                 'parser',
                 'success',
                 'status',
                 'committed'],

            'commit_jobs':
                ['label',
                 'date',
                 'description',
                 'log',
                 'mode',
                 'job_status',
                 'job_step',
                 'job_successes',
                 'job_fails',
                 'job_passes',
                 'job_duplicates',
                 'no_of_publications'],

            'commits':
                ['label',
                 'action_index',
                 'parse_label',
                 'parse_action_index',
                 'date',
                 'doi',
                 'publisher',
                 'journal',
                 'title',
                 'publication_type',
                 'no_of_authors',
                 'author_names',
                 'affiliations',
                 'received',
                 'accepted',
                 'published',
                 'normalized_received',
                 'normalized_accepted',
                 'normalized_published',
                 'normalized_publisher',
                 'normalized_journal',
                 'success',
                 'status',
                 'passed',
                 'duplicate'],

            'pub':
                ['doi',
                 'publisher',
                 'journal',
                 'title',
                 'publication_type',
                 'no_of_authors',
                 'author_names',
                 'affiliations',
                 'received',
                 'accepted',
                 'published',
                 'normalized_received',
                 'normalized_accepted',
                 'normalized_published',
                 'normalized_publisher',
                 'normalized_journal'
                 ]

                }

    return registered_tables

def sanity_check(name, columns):
    """
    Checks if ``name`` and ``columns`` are in the registered tables

    Parameters
    ----------
    name : str
        Table name
    columns : list
        List of column names

    """

    registered_tables = get_registered_tables()

    allowed_names = registered_tables.keys()

    if name not in allowed_names:
        raise PermissionError(f'Table name not in registered tables. Allowed names: {list(allowed_names)}')

    allowed_columns = registered_tables[name]

    if columns != allowed_columns:
        raise PermissionError(f'Incorrect table columns found. Expected columns: {allowed_columns}')

def check_column(name, column):
    """
    Checks if ``column`` is in the registered table called ``name``

    """

    registered_tables = get_registered_tables()

    allowed_names = registered_tables.keys()

    if name not in allowed_names:
        raise PermissionError(f'Table name not in registered tables. Allowed names: {list(allowed_names)}')

    allowed_columns = registered_tables[name]

    if not column in allowed_columns:
        raise PermissionError(f'Incorrect table column "{column}" given. Expected one of the following columns: {allowed_columns}')
