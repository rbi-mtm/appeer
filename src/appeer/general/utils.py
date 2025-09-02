"""Includes various utility functions"""

import os
import glob
import re
import time
import json
import zipfile

from shutil import make_archive, rmtree
from datetime import datetime
from random import randint
from difflib import SequenceMatcher

import click

from appeer.db.tables.pub import FilteredPub as _FilteredPub

def load_json(json_filename):
    """
    Load a JSON file to a list of dictionaries

    Parameters
    ----------
    json_filename : str
        Input JSON filename

    Returns
    -------
    list
        List of dictionaries generated from the JSON file

    """

    with open(json_filename, encoding='utf-8-sig') as f:
        data = json.load(f)

    return data

def json2list(json_filename):
    """
    Convert a JSON file to a Python list containing only article URLs

    If an article URL cannot be found for a given entry,
        'no_url' will be written into the output list

    Parameters
    ----------
    json_filename : str
        Input JSON filename

    Returns
    -------
    url_list : list
        List of URLs parsed from the JSON file

    """


    publications = load_json(json_filename)

    url_list = []

    for publication in publications:

        try:
            url = publication['article_url']

        except KeyError:
            url = 'no_url'

        url_list.append(url)

    return url_list

def json2txt(json_filename, text_filename):
    """
    Convert a JSON file to a text file containing only article URLs

    The URLs are extracted using the ``'article_url'``
        keys from the JSON entries

    Parameters
    ----------
    json_filename : str
        Input JSON filename
    text_filename : str
        Output textfile filename
    """

    url_list = json2list(json_filename)

    with open(text_filename, 'w+', encoding='utf-8') as f:
        for url in url_list:
            f.write(f'{url}\n')

def txt2list(text_filename):
    """
    Convert a text file to a Python list containing only article URLs

    Each URL should be written in a separate line.

    The URLs can be written either as a full URL or a DOI.
        E.g., the following entries are equally valid:

    https://pubs.rsc.org/en/content/articlelanding/2023/ob/d3ob00424d
    10.1039/D3OB00424D

    Valid entries start with 'https://' or need to be
        in DOI format: 10.prefix/suffix
    If the entry format is invalid, 'no_url'
        is written into the output list

    If any line contains more than one entry, an exception is raised

    Parameters
    ----------
    text_filename : str
        Input text filename

    Returns
    -------
    url_list : list
        List of URLs parsed from the text file

    """

    url_list = []

    with open(text_filename, 'r', encoding='utf-8') as f:

        lines = f.readlines()

    for i, line in enumerate(lines):

        entry = line.split('\n')[0]

        if len(entry.split(' ')) > 1:
            raise ValueError(f'More than one URL entry on line #{i} in file {text_filename}')

        if entry.startswith('https://'):
            url_list.append(entry)

        elif check_doi_format(entry):
            url_list.append(f'https://doi.org/{entry}')

        else:
            url_list.append('no_url')

    return url_list

def get_doi_substring(entry):
    """
    Extracts DOI from a string

    If the regex finds multiple matches, only the first occurence is returned

    Parameters
    ----------
    entry : str
        String in which to search for DOI

    Returns
    -------
    doi : str | None
        DOI matched in the string; None if no match was found

    """

    if not isinstance(entry, str):
        doi = None

    else:

        _doi = re.findall(r'10\.\S+/\S+', entry)

        if _doi:
            doi = _doi[0]

        else:
            doi = None

    return doi

def check_doi_format(entry):
    """
    Check if a string is in DOI format (10.prefix/suffix)

    Parameters
    ----------
    entry : str
        String to be tested if it is in DOI format

    Returns
    -------
    is_doi_format : bool
        True if ``entry`` is in DOI format, False if it is not

    """

    starts_w_10 = entry.startswith('10')
    has_prefix_suffix = len(re.split(r'^10\.|/', entry)) == 3

    is_doi_format = starts_w_10 and has_prefix_suffix

    return is_doi_format

def aff_list2str(aff_list):
    """
    Transform a list of affiliations to a string

    As sqlite3 does not support adding Python lists as values,
        this function is used to transform a list of affiliations
        to a single string.

    The affiliations are obtained by parsing in a "list of list of str" data
        type. Each entry corresponds to one or more affiliation(s) of an
        author. An example affiliation list might look like:

        [
            [affiliation0],
            [affiliation0, affiliation1],
            ...
        ]

    This function will transform this list to the following string:

        affiliation0?_?affiliation0!_!affiliation1?_?...

    I.e., "?_?" is the separator for the affiliations of different authors,
        while "!_!" is the separator for the affiliations of a single author

    Parameters
    ----------
    aff_list : list of list of str
        List of affiliations

    Returns
    -------
    aff_str : str
        The affiliation list concatenated to a single string

    """

    aff_str = '?_?'.join([
        '!_!'.join(aff) for aff in aff_list
        ])

    return aff_str

def aff_str2list(aff_str):
    """
    Inverts the transformation performed by aff_list2str

    Parameters
    ----------
    aff_str : str
        The affiliation list concatenated to a single string

    Returns
    -------
    aff_list : list of list of str
        List of affiliations

    """

    aff_list = [
            aff.split('!_!')
            for aff in aff_str.split('?_?')
            ]

    return aff_list

def publication_types_unpack(publication_types_pack):
    """
    Unpacks the publication types listed by appeer.db.tables.pub methods

    Parameters
    ----------
    publication_types_pack : str
        Publication types as given by get_publisher_summary()

    Returns
    -------
    publication_types : list of str
        List of publication types

    """

    publication_types = publication_types_pack.split('|,')

    if publication_types[-1].endswith('|'):
        publication_types[-1] = publication_types[-1][:-1]

    return publication_types

def compare_strings(string1, string2):
    """
    Obtains the similarity metric between two strings

    Note: both strings are first made lowercase using casefold()

    Parameters
    ----------
    string1 : str
        A string to be compared with another string
    string2 : str
        A string to be compared with another string

    Returns
    -------
    ratio : float
        A measure of the strings’ similarity in the range [0, 1]

    """

    string1 = string1.casefold()
    string2 = string2.casefold()

    ratio = SequenceMatcher(None, string1, string2).ratio()

    return ratio

def get_current_datetime():
    """
    Get current datetime in the ``%Y%m%d-%H%M%S`` format

    Returns
    -------
    timestr : str
        Current datetime in ``%Y%m%d-%H%M%S`` format.

    """

    timestr = time.strftime("%Y%m%d-%H%M%S")

    return timestr

def convert_time_string(time_string):
    """
    Convert datetime from a string in ``%Y%m%d-%H%M%S`` format
        to a ``datetime.datetime`` object

    Parameters
    ----------
    time_string : str
        Datetime string in ``%Y%m%d-%H%M%S`` format 

    Returns
    -------
    datetime.datetime
        datetime.datetime object obtained from the converted datetime string

    """

    datetime_object = datetime.strptime(time_string, '%Y%m%d-%H%M%S')

    return datetime_object

def human_datetime(time_string):
    """
    Convert a string in ``%Y%m%d-%H%M%S`` format
        to a human-readable date and time string

    Parameters
    ----------
    time_string : str
        Datetime string in ``%Y%m%d-%H%M%S`` format

    Returns
    -------
    human_time : str
        Date and time in nice format (e.g. Dec 25th 2024)

    """

    dt = convert_time_string(time_string)
    human_time = datetime.strftime(dt,
            '%a %d %B %Y, %H:%M:%S')

    return human_time

def get_runtime(start_time, end_time):
    """
    Calculate runtime between ``end_time`` and ``start_time``

    Parameters
    ----------
    start_time : datetime.datetime
        Start time
    end_time : datetime.datetime
        End time

    Returns
    -------
    delta : str
        Runtime in ``%H:%M:%S`` format

    """

    delta = end_time - start_time

    return str(delta)

def random_number():
    """
    Generate a random number as a string

    Returns
    -------
    random_no : str
        Random number between 0 and 100

    """

    random_no = str(randint(0, 100))

    return random_no

def write_text_to_file(filepath, text_data):
    """
    Write text to a file

    Parameters
    ----------
    filepath : str
        Output file path
    text_data : str
        Text data to be written into a file

    """

    with open(filepath, 'w+', encoding='utf-8') as f:
        f.write(text_data)

def abspath(path):
    """
    Get the absolute path

    This function combines ``os.path.realpath`` and ``os.path.expanduser``,
        so the final absolute path contains resolved symbolic links
        and the expanded ``~`` user directory

    Parameters
    ----------
    path : str
        Any path

    Returns
    -------
    absolute_path : str
        Absolute path with resolved symbolic links
            and expanded home directory (~)

    """

    absolute_path = os.path.realpath(os.path.expanduser(path))

    return absolute_path

def archive_directory(output_filename, directory_name):
    """
    Create a ZIP archive from a directory called ``directory_name``

    Parameters
    ----------
    output_filename : str
        Name of the output .zip directory
    directory_name : str
        Path to the directory to be archived
    """

    if output_filename.endswith('.zip'):
        output_filename = output_filename[:-4]

    make_archive(base_name=output_filename,
            format='zip', base_dir=directory_name)

def archive_list_of_files(output_filename, file_list):
    """
    Create a ZIP archive from a list of files

    Parameters
    ----------
    output_filename : str
        Name of the output .zip directory
    file_list : list
        List of files to be archived

    """

    with zipfile.ZipFile(output_filename, 'w') as zipper:
        for f in file_list:
            zipper.write(f, os.path.basename(f),
                    compress_type=zipfile.ZIP_DEFLATED)

def extract_archive(zip_filename, target_directory):
    """
    Extract a ZIP archive to ``target_directory``

    If the ``target_directory`` does not exist, it will be created

    Parameters
    ----------
    zip_filename : str
        Path to the ZIP archive to be extracted
    target_directory : str
        Path to the directory in which the ZIP archive will be extracted

    Returns
    -------
    success : bool
        True if extraction succeeded, False if it did not

    """

    success = False

    zip_filename = abspath(zip_filename)
    target_directory = abspath(target_directory)

    if not file_exists(zip_filename):
        return success

    if not zipfile.is_zipfile(zip_filename):
        return success

    if not directory_exists(target_directory):

        try:
            os.makedirs(target_directory)

        except PermissionError:
            return success

    with zipfile.ZipFile(zip_filename, 'r') as unzipper:
        unzipper.extractall(path=target_directory)

    success = True

    return success

def delete_directory(directory_name, verbose=True):
    """
    Delete directory called ``directory_name``

    Parameters
    ----------
    directory_name : str
        Path to the directory to be deleted
    verbose : bool
        If True, echo messages

    """

    if directory_exists(directory_name):

        rmtree(directory_name)

        if not directory_exists(directory_name):
            if verbose:
                click.echo(f'Deleted {directory_name}')

        else:
            if verbose:
                click.echo(f'Could not delete {directory_name}')

    else:
        if verbose:
            click.echo(f'Directory {directory_name} does not exist')

def delete_file(file_name):
    """
    Delete file called ``file_name``

    Parameters
    ----------
    file_name : str
        Path to the file to be deleted

    """

    if file_exists(file_name):
        os.remove(file_name)

        if not file_exists(file_name):
            click.echo(f'Deleted {file_name}')

        else:
            click.echo(f'Could not delete {file_name}')

    else:
        click.echo(f'File {file_name} does not exist')

def directory_exists(directory_path):
    """
    Check if directory ``directory_path`` exists

    Parameters
    ----------
    directory_path : str
        Path to the directory whose existence is checked
 
    Returns
    ----------
    exists : bool
        True if directory exists, False if it does not

    """

    exists = os.path.isdir(directory_path)

    return exists

def file_exists(file_path):
    """
    Check if file at ``file_path`` exists

    Parameters
    ----------
    file_path : str
        Path to the file whose existence is checked
 
    Returns
    -------
    exists : bool
        True if file exists, False if it does not

    """

    exists = os.path.isfile(file_path)

    return exists

def is_list_of_str(obj):
    """
    Check whether an object is a (nonempty) list of strings or a single string

    Parameters
    ----------
    obj : Any
        Object to be checked

    Returns
    -------
    check_list_of_str : bool
        True if the passed object is a nonempty list of strings
            or a single nonempty string

    """

    check_list_of_str = True

    if not (obj and isinstance(obj, (list, str))):
        check_list_of_str = False

    if isinstance(obj, list):
        if not all(s and isinstance(s, str) for s in obj):
            check_list_of_str = False

    return check_list_of_str

def file_list_readable(file_list):
    """
    Check if a list of files exist and are readable

    The function also accepts a single path given as a string

    Parameters
    ----------
    file_list : list of str | str
        List of file paths to check for existence and readability

    Returns
    -------
    files_readability : dict
        Dictionary of form {path1: True, path2: False, ...},
            where the keys are the absolute file paths and the values are
            True/False for readable/unreadable

    """

    if not is_list_of_str(file_list):
        raise TypeError('The file list must be provided as a list of strings or a single string.')

    if isinstance(file_list, str):
        file_list = [file_list]

    files_readability = {
            abspath(f): os.access(abspath(f), os.R_OK)\
                    and os.path.isfile(abspath(f))
                for f in file_list
            }

    return files_readability

def is_directory_empty(directory_path):
    """
    Check if directory ``directory_path`` is not empty

    Parameters
    ----------
    directory_path : str
        Path to the directory that is checked for existence of any content
 
    Returns
    ----------
    empty : bool
        True if directory is empty, False if it is not

    """

    exists = directory_exists(directory_path)

    if exists:
        empty = not os.listdir(directory_path)

    else:
        click.echo(f'Directory {directory_path} does not exist.')
        empty = True

    return empty

def get_files_in_dir(directory_path):
    """
    Get a list of files in a directory (excluding subdirectories)

    Parameters
    ----------
    directory_path : str
        Path to the directory in which to search for files
    Returns
    ----------
    files : list
        List of filepaths in the searched directory

    """

    files = glob.glob(f'{directory_path}/*')
    files = [f for f in files if os.path.isfile(f)]

    return files

def delete_directory_files(directory_path):
    """
    Deletes files in a directory 
    (does not delete subdirectories and their file content)

    Parameters
    ----------
    directory_path : str
        Path to the directory whose files are to be deleted

    """

    files = get_files_in_dir(directory_path)

    if files:

        for f in files:

            try:
                os.remove(f)

            except PermissionError:
                click.echo(f'Could not delete file {f}.')
    else:
        click.echo('Nothing to delete.')
        return

    files_after = get_files_in_dir(directory_path)

    if not files_after:
        click.echo(f'Files in {directory_path} deleted.')

    else:
        click.echo(f'Could not delete all files in {directory_path}')

def delete_directory_content(directory_path):
    """
    Deletes everything in a directory

    Parameters
    ----------
    directory_path : str
        Path to the directory whose contents are to be deleted

    """

    contents = glob.glob(f'{directory_path}/*')

    if len(contents) == 0:
        click.echo('Nothing to delete.')
        return

    for root, dirs, files in os.walk(directory_path):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            rmtree(os.path.join(root, d))

    contents_after = glob.glob(f'{directory_path}/*')

    if not contents_after:
        click.echo(f'Contents of {directory_path} deleted.')

    else:
        click.echo(f'Could not delete all files in {directory_path}')

def check_FilteredPub_type(filtered_pubs):
    """
    Checks whether ``filtered_pubs`` is a list of ``FilteredPub`` instances

    Parameters
    ----------
    filtered_pubs : list of appeer.db.tables.pub.FilteredPub
        Publications obtained from ``pub.db`` searches

    Raises
    ------
    ValueError
        If ``filtered_pubs`` is not a list of ``FilteredPub``

    """

    if not isinstance(filtered_pubs, list):
        raise ValueError('filtered_pubs must be a list of appeer.db.tables.pub.FilteredPub')

    if filtered_pubs and not all(isinstance(publication, _FilteredPub)
                for publication in filtered_pubs):
        raise ValueError('filtered_pubs must be a list of appeer.db.tables.pub.FilteredPub')
