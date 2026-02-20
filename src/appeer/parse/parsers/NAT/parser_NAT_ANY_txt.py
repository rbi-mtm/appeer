"""Text parser for any Nature journal"""

import functools

from appeer.general import utils as _utils

from appeer.parse.parsers.parser import Parser
from appeer.parse.parsers import date_utils
from appeer.parse.parsers import soup_utils

class Parser_NAT_ANY_txt(Parser,
        publisher_code='NAT',
        journal_code='ANY',
        data_type='txt'):
    """
    Text parser for any Nature journal

    """

    @staticmethod
    def check_publisher_journal(input_data, parser='lxml'):
        """
        Checks whether ``input_data`` corresponds to Nature

        Parameters
        ----------
        input data : bs4.BeautifulSoup | str
           Data loaded into ``BeautifulSoup`` or a path to a file to be parsed
        parser : str
            The parser used by ``BeautifulSoup``

        Returns
        -------
        is_NAT_ANY : bool
            True if ``input_data`` corresponds to Nature;
                False otherwise

        """

        is_NAT_ANY = False

        soup, exception = soup_utils.convert_2_soup(input_data, parser=parser)

        if not exception:

            publisher = soup_utils.get_meta_content(
                    soup=soup,
                    attr_value='dc.publisher')

            if publisher:
                is_NAT_ANY = 'Nature' in publisher

            else:
                pass

        return is_NAT_ANY, exception

    def __init__(self, input_data, data_type='txt', parser='lxml', #pylint:disable=too-many-arguments
            publishers_index=None, publisher_journals=None):
        """
        Load the inputted data into ``self._input_data``

        Parameters
        ----------
        input_data : bs4.BeautifulSoup | str
            Data loaded into BeautifulSoup or a path to a file to be parsed
        data_type : str
            Input data type.
        parser : str
            The parser used by ``BeautifulSoup``
        publishers_index : dict | None
            The ../publishers_index.json file loaded to a dict
                If None, it will be loaded.
        publisher_journals : dict | None
            ./<publisher_code>/<publisher_code>_journals.json loaded to a dict
                If None, it will be loaded

        """

        super().__init__(input_data=input_data,
                data_type=data_type,
                parser=parser,
                publishers_index=publishers_index,
                publisher_journals=publisher_journals)

    def _parse_NAT_date(self, date_type):
        """
        Parses the received/published/accepted dates from any Nature journal

        Parameters
        ----------
        date_type : str
            One of ('Received', 'Accepted', 'Published')

        Returns
        -------
        _date : str | None
            The parsed date; None if parsing failed

        """

        if date_type not in('Received', 'Accepted', 'Published'):
            raise ValueError('Invalid date_type inputted into _parse_NAT_date; must be one of ("Received", "Accepted", "Published").')

        _date = None

        li_list = self._input_data.find_all('li',
                class_='c-bibliographic-information__list-item')

        li_list.extend(self._input_data.find_all('li',
                class_='c-article-identifiers__item'))

        if li_list:

            for li in li_list:

                try:
                    text = li.text

                except AttributeError:
                    pass

                else:

                    if date_type in text:

                        try:
                            _date = date_utils.get_d_M_y(text)[0]

                        except (IndexError, TypeError):
                            pass

                        else:
                            break

        return _date

    @functools.cached_property
    def doi(self):
        """
        Get the publication DOI

        Returns
        -------
        _doi : str | None
            The publication DOI

        """

        _doi = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='DOI')

        return _doi

    @functools.cached_property
    def publisher(self):
        """
        Get the publisher

        Returns
        -------
        _publisher : str | None
            The paper publisher
        
        """

        _publisher = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='dc.publisher')

        return _publisher

    @functools.cached_property
    def journal(self):
        """
        Get the journal

        Returns
        -------
        _journal : str | None
            The publication journal
        
        """

        _journal = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='citation_journal_title')

        return _journal

    @functools.cached_property
    def title(self):
        """
        Get the publication title

        Returns
        -------
        _title : str | None
            Publication title
        
        """

        _title = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='dc.title')

        return _title

    @functools.cached_property
    def publication_type(self):
        """
        Get the publication type

        Returns
        -------
        _publication type : str | None
            Publication type
        
        """

        _publication_type = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='citation_article_type')

        return _publication_type

    @functools.cached_property
    def no_of_authors(self):
        """
        Get the number of publication authors

        Returns
        -------
        _no_of_authors : int | None
            Number of publication authors

        """

        #
        # If the author names cannot be obtained, immediately fail
        #

        _no_of_authors = None

        if not self.author_names:
            return None

        _no_of_authors = len(self.author_names)

        return _no_of_authors

    @functools.cached_property
    def author_names(self): #pylint:disable=too-many-branches
        """
        Get the author names

        Returns
        -------
        _author_names : list of str | None
            List of author names;
                each entry corresponds to the name of a single author
        
        """

        _author_names = soup_utils.get_meta_content(
                soup=self._input_data,
                attr_value='citation_author',
                attr_key='name'
                )

        if _author_names:

            if isinstance(_author_names, str):
                _author_names = [_author_names]

            _author_names = [name.replace('\xa0', ' ')
                             for name in _author_names]

        return _author_names

    @functools.cached_property
    def affiliations(self):
        """
        Get the author affiliations

        Returns
        -------
        _affiliations : list of list of str | None
            List of affiliations;
                each entry corresponds to one or more affiliation(s)
                of a single author
        
        """

        #
        # If the number of authors cannot be obtained, immediately fail
        #
        if not self.no_of_authors:
            return None

        _affiliations = []

        search_ended = True

        pivot = self._input_data.find('meta', attrs={'name': 'citation_author_institution'})

        if pivot:

            search_ended = False

            try:
                _affiliations.append([pivot['content']])

            except KeyError:
                return None

        while not search_ended:

            pivot = pivot.find_next()

            try:

                match pivot.attrs['name']:

                    case 'citation_author_institution':

                        try:
                            _affiliations[-1].append(pivot['content'])

                        except KeyError:
                            return None

                    case 'citation_author':
                        _affiliations.append([])

                    case _:
                        search_ended = True

            except AttributeError:
                return _affiliations or None

        _affiliations = _affiliations or None

        if _affiliations and\
                (len(_affiliations) != self.no_of_authors or\
                not all(_affiliations)):

            _affiliations = None

        return _affiliations

    @functools.cached_property
    def received(self):
        """
        Get the date when the publication was received

        Returns
        -------
        _received : str | None
            The date when the publication was received
        
        """

        _received = self._parse_NAT_date('Received')

        return _received

    @functools.cached_property
    def accepted(self):
        """
        Get the date when the publication was accepted

        Returns
        -------
        _accepted : str | None
            The date when the publication was accepted
        
        """

        _accepted = self._parse_NAT_date('Accepted')

        return _accepted

    @functools.cached_property
    def published(self):
        """
        Get the date when the publication was published

        Returns
        -------
        _published : str | None
            The date when the publication was published
        
        """

        _published = self._parse_NAT_date('Published')

        return _published

    @functools.cached_property
    def normalized_received(self):
        """
        Normalize the ``received`` date to ISO format (YYYY-MM-DD)

        Returns
        -------
        _normalized_received : str
            Date in YYYY-MM-DD format

        """

        _normalized_received = date_utils.normalize_d_M_y(self.received)

        return _normalized_received

    @functools.cached_property
    def normalized_accepted(self):
        """
        Normalize the ``accepted`` date to ISO format (YYYY-MM-DD)

        Returns
        -------
        _normalized_accepted : str
            Date in YYYY-MM-DD format

        """

        _normalized_accepted = date_utils.normalize_d_M_y(self.accepted)

        return _normalized_accepted

    @functools.cached_property
    def normalized_published(self):
        """
        Normalize the ``published`` date to ISO format (YYYY-MM-DD)

        Returns
        -------
        _normalized_published : str
            Date in YYYY-MM-DD format

        """

        _normalized_published = date_utils.normalize_d_M_y(self.published)

        return _normalized_published
