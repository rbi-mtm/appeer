"""Commit parsed metadata to the ``pub.db`` database"""

from appeer.general import utils as _utils

from appeer.jobs.action import Action
from appeer.db.pub_db import PubDB

from appeer.parse.default_metadata import default_metadata

from appeer.commit import commit_reports as reports

class CommitAction(Action, action_type='commit'): #pylint:disable=too-many-instance-attributes
    """
    Commit parsed metadata to the ``pub.db`` database

    A commit action attempts to insert metadata corresponding to a single
        parse action to the ``pub.db`` database.

    The ``pub.db`` database may contain one and only one entry for a given
        DOI. Therefore, if a commit action attempts to insert an entry
        with a DOI that already exists in ``pub.db``, one of the following
        may happen:

            (1) The entry is rejected; i.e. the commit action does nothing.
                    This is the default behavior.

            (2) The entry is overwritten.
                    This behavior is activated if the ``overwrite`` parameter
                    of self.run() is set to True.

    Instances of the CommitAction class have dynamically created properties
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
    parse_label : str
        Label of the parse job that the metadata corresponds to
    parse_action_index : int
        Index of the parse action that the input file corresponds to
    date : str
        Date and time of the job creation/run; mutable
    doi : str
        DOI of the publication
    publisher : str
        Publisher
    journal : str
        Publication journal
    title : str
        Title of the publication
    publication_type : str
        Type of publication
    no_of_authors : int
        Number of publication authors
    author_names : list of str
        Author names
    affiliations : list of str
        Author affiliations
    received : str
        Date of the publication reception
    accepted : str
        Date of the publication acceptance
    published : str
        Date of publication
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
    success : str
        Whether the action executed successfully; one of ('T', 'F');
            note that success will be 'T' even if the entry is
            cleanly rejected
    status : str
        Action status; one of ('I', 'W', 'R', 'E', 'X'); mutable
    passed : str
        Whether the metadata was entered into ``pub.db``;
            one of ('T', 'F'); mutable
    duplicate : str
        Whether ``self.doi`` already exists in ``pub.db`` before committing;
            one of ('T', 'F'); mutable

    """


    def __init__(self, label=None, action_index=None, action_mode='read'):
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
                action_mode=action_mode)

    def new_action(self,
            commit_entry,
            label=None,
            action_index=None):
        """
        Creates a new commit action for a given commit entry

        Parameters
        ----------
        commit_entry : appeer.commit.commit_packer._CommitEntry
            Named tuple with fields
                ('scrape_label', 'scrape_action_index', 'metadata')
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
                parse_label=commit_entry.parse_label,
                parse_action_index=commit_entry.parse_action_index,
                status='W',
                **commit_entry.metadata)

    def run(self, overwrite=False, _queue=None):
        """
        Run the commit action

        A commit action attempts to add an entry to the ``pub`` table
            of the ``pubs.db`` database.

        Each entry in the ``pub`` table must have a unique ``doi`` value.

            If an entry containing a DOI value already existing in the table
                is attempted to be added to the database, the ``overwrite``
                parameter governs the behavior of this method:

                (1) If ``overwrite == False``, the entry is not inserted

                (2) If ``overwrite == True``, the entry with the given
                    DOI is updated

        If ``queue`` is given, messages will be sent to the ``queue``
            and logged in the job log file

        Parameters
        ----------
        overwrite : bool
            If False, ignore a duplicate DOI entry (default);
            if True, overwrite a duplicate DOI entry;
            if the given DOI is unique, this parameter has no impact
        queue : queue.Queue
            If given, messages will be logged in the job log file

        """

        start_datetime = _utils.get_current_datetime()

        self._queue = _queue

        self._action_mode = 'write'
        self.status = 'R'

        self.date = start_datetime

        self._aprint(reports.commit_action_start(self))

        pub = PubDB().pub

        metadata = {meta: getattr(self, meta)
                for meta in default_metadata()
                }

        duplicate, inserted = pub.add_entry(overwrite=overwrite, **metadata)

        pub._con.close() #pylint:disable=protected-access

        if duplicate:
            self.duplicate = 'T'

        else:
            self.duplicate = 'F'

        if inserted:
            self.passed = 'T'

        else:
            self.passed = 'F'

        self._aprint(reports.commit_action_end(action=self))

        self.success = 'T'

        self.status = 'X'
