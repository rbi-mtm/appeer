"""Parse a single file"""

import os
import inspect
import datetime
import hashlib

from appeer import __version__

from appeer.general import utils as _utils

from appeer.jobs.action import Action

from appeer.parse.parsers.preparser import Preparser
from appeer.parse import parse_reports as reports

class ParseAction(Action, action_type='parse'): #pylint:disable=too-many-instance-attributes
    """
    Parse a single file

    Instances of the ParseAction class have dynamically created properties
        corresponding to the columns of the ``scrapes`` table in the
        ``jobs`` database

        Some of these properties are mutable; changing their value will
        update the value in the ``jobs`` database. The values of the
        non-mutable properties are set using ``self.new_action(**kwargs)``.
        The values of these properties may be edited only if
        ``self._action_mode == 'write'

    List of the dynamically created properties:

    Dynamic Properties
    ------------------
    label : str
        Label of the job that the action corresponds to
    action_index : int
        Index of the action within the job
    scrape_label : str
        Label of the scrape job that the input file corresponds to
            (can be None if the input file does not come from a scrape job)
    scrape_action_index : int
        Index of the scrape action that the input file corresponds to
            (can be None if the input file does not come from a scrape job)
    date : str
        Date and time of the job creation/run; mutable
    input_file : str
        Path to the input file to be parsed
    doi : str
        DOI of the publication; mutable
    publisher : str
        Publisher; mutable
    journal : str
        Publication journal; mutable
    title : str
        Title of the publication; mutable
    publication_type : str
        Type of publication; mutable
    no_of_authors : int
        Number of publication authors; mutable
    affiliations : list of str
        Author affiliations; mutable
    received : str
        Date of the publication reception; mutable
    accepted : str
        Date of the publication acceptance; mutable
    published : str
        Date of publication; mutable
    normalized_received : str
        Date of the publication reception in YYYY-MM-DD format
    normalized_accepted : str
        Date of the publication acceptance in YYYY-MM-DD format
    normalized_published : str
        Date of publication in YYYY-MM-DD format
    normalized_publisher : str
        Publisher in the standard format;
            as defined in parse/parsers/publishers_index.json
    normalized_journal : str
        Journal in the standard format;
            as defined in parse/parsers/PUBLISHER/PUBLISHER_journals.json
    parser : str
        Name of the parser class used to parse the input file; mutable
    success : str
        Whether the action executed successfully; one of ('T', 'F'); mutable
    status : str
        Action status; one of ('I', 'W', 'R', 'E', 'X'); mutable
    committed : str
        Whether the data corresponding to this action was committed;
            one of ('T', 'F'); mutable

    """

    def __init__(self, label=None, action_index=None, action_mode='read',
                 _db=None):
        """
        Connects to the job database and sets the action label and index

        Parameters
        ----------
        label : str
            Label of the job that the action corresponds to
        action_index : int
            Index of the action within the corresponding job

        """

        super().__init__(label=label,
                action_index=action_index,
                action_mode=action_mode,
                _db=_db)

    def new_action(self,
            parse_entry,
            label=None,
            action_index=None):
        """
        Creates a new parse action for a given parse entry

        Parameters
        ----------
        parse_entry : appeer.parse.parse_packer._ParseEntry
            Named tuple with fields
                ('scrape_label', 'scrape_action_index', 'filepath')
        label : str
            Label of the job that the action corresponds to
        action_index : int
            Index of the action within the corresponding job

        """

        self._action_mode = 'write'

        if label:
            self.label = label

        if action_index:
            self.action_index = action_index

        self._initialize_action_common(
                scrape_label=parse_entry.scrape_label,
                scrape_action_index=parse_entry.scrape_action_index,
                input_file=parse_entry.filepath,
                status='W')

    def run(self,
            _queue=None,
            publishers_index=None,
            publisher_journals_dict=None,
            **kwargs):
        """
        Run the parse action

        If ``queue`` is given, messages will be sent to the ``queue``
            and logged in the job log file

        The ``publishers_index`` should be either ``None`` or the
            ./parsers/publishers_index.json file loaded to a dict.

        Usually, ParseJob will load the file once per job and
            pass it to all the parse actions.

        The ``publisher_journals_dict`` should be either ``None`` or a
            dictionary whose keys are publisher codes and whose values
            are the corresponding loaded

            ./parsers/<publisher_code>/<publisher_code>_journals.json

            files. If <publisher_code> is not present in the dictionary,
            the file will be loaded.

        The rest of the arguments will be passed to the Preparser.
            They may be used to accelerate determining the appropriate
            parser for the given input file.

        For more details, see the documentation of the Preparser class

        Parameters
        ----------
        queue : queue.Queue
            If given, messages will be logged in the job log file
        publishers_index : dict | None
            The ./parsers/publishers_index.json file loaded to a dict
                If None, it will be loaded by the parser class
        publisher_journals_dict : dict | None
            Dictionary holding the loaded publisher journals JSON files;
                If None or publisher code key not in dictionary,
                the necessary file will be loaded by the parser class

        Keyword Arguments
        -----------------
        publishers : str | list of str | None
            List of candidate parser publisher codes
        journals : str | list of str | None
            List of candidate parser journal codes
        data_types : str | list of str | None
            List of candidate parser data types;
                currently, only 'txt' is supported

        """

        start_datetime = _utils.get_current_datetime()

        self._queue = _queue

        self._action_mode = 'write'
        self.status = 'R'

        self.date = start_datetime

        parser_class, loaded_data = self._determine_parser(**kwargs)

        if publisher_journals_dict is None:
            publisher_journals_dict = {}

        try:
            self.parser = parser_class.__name__

        except AttributeError:
            self.parser = None
            self.success = 'F'

        self._aprint(reports.parse_action_start(self))

        if not self.parser:
            self._aprint('Preparser failed to determine the appropriate parser. Skipping this entry.\n')

        else:

            publisher_code = self.parser.split('_')[1]

            try:
                publisher_journals = publisher_journals_dict[publisher_code]

            except (KeyError, AttributeError):

                parser_dir = os.path.dirname(
                        inspect.getfile(parser_class)
                        )

                publisher_journals_json = f'{publisher_code}_journals.json'

                publisher_journals = _utils.load_json(
                        os.path.join(parser_dir, publisher_journals_json)
                        )

                publisher_journals_dict[f'{publisher_code}'] =\
                        publisher_journals

            parser = parser_class(self.input_file,
                    publishers_index=publishers_index,
                    publisher_journals=publisher_journals)

            self._aprint(reports.parsing_report(parser))

            for meta in parser.metadata_list:
                value = getattr(parser, meta)
                if value is not None:
                    setattr(self,
                            meta,
                            value)

            for field, value in parser.provenance.items():
                if value is not None:
                    setattr(self, field, value)

            if parser.success:
                self.success = 'T'

            else:
                self.success = 'F'

        if not self.parser:
            with open(self.input_file, 'rb') as input_file:
                raw_sha256 = hashlib.sha256(input_file.read()).hexdigest()
            self.raw_sha256 = raw_sha256
            self.package_version = __version__
            self.parsed_at = datetime.datetime.now(datetime.UTC).isoformat()
            self.invalid_fields = list(parser_class.metadata_list) if parser_class else [
                'doi', 'publisher', 'journal', 'title', 'publication_type',
                'no_of_authors', 'author_names', 'affiliations', 'received',
                'accepted', 'published', 'normalized_received',
                'normalized_accepted', 'normalized_published',
                'normalized_publisher', 'normalized_journal']
            self.warnings = ['unsupported_layout']

        self.status = 'X'

    def _determine_parser(self, **kwargs):
        """
        Determines the appropriate Parser subclass for ``self.filepath``

        Keyword Arguments
        -----------------
        publishers : str | list of str | None
            List of candidate parser publisher codes
        journals : str | list of str | None
            List of candidate parser journal codes
        data_types : str | list of str | None
            List of candidate parser data types;
                currently, only 'txt' is supported

        Returns
        -------
        parser : appeer...Parser_<PUBLISHER>_<JOURNAL>_<DATA_TYPE> | None
            The appropriate Parser subclass; None if search failed
        loaded_data : bs4.BeautifulSoup | ? | None
            The data loaded into a BeautifulSoup object (for "txt" data type);
            ? is left as placeholder for other data types;
            None if the search failed

        """

        preparser = Preparser(filepath=self.input_file,
                publishers=kwargs['publishers'],
                journals=kwargs['journals'],
                data_types=kwargs['data_types'])

        parser_class, loaded_data = preparser.determine_parser()

        return parser_class, loaded_data

    def mark_as_committed(self):
        """
        Marks the parse action as committed.

        If the action does not exist, does nothing.

        """

        if self._action_exists:

            self._action_mode = 'write'
            self.committed = 'T'

    def mark_as_uncommitted(self):
        """
        Marks the parse action as uncommitted.

        If the action does not exist, does nothing.

        """

        if self._action_exists:

            self._action_mode = 'write'
            self.committed = 'F'
