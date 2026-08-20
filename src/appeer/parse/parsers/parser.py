"""Base class shared by strict publisher parsers."""

import abc
import datetime
import functools
import hashlib
import inspect
import json
import os
import subprocess

from appeer import __version__
from appeer.general import utils as _utils
from appeer.parse.default_metadata import default_metadata
from appeer.parse.metadata import normalize_known, validate_metadata
from appeer.parse.parsers import soup_utils


class Parser(abc.ABC):
    """Base class for complete, evidence-backed publication parsers."""

    @classmethod
    def _define_metadata_list(cls):
        cls.metadata_list = default_metadata()

    def __init_subclass__(cls, publisher_code, journal_code, data_type):
        module_bits = os.path.basename(inspect.getfile(cls)).split('.')[0].split('_')
        class_bits = cls.__name__.split('_')
        expected_module = ['parser', publisher_code, journal_code, data_type]
        expected_class = ['Parser', publisher_code, journal_code, data_type]
        if module_bits != expected_module or class_bits != expected_class:
            raise ValueError(f'Parser naming convention not respected by {cls.__name__}.')
        if not isinstance(cls.__dict__.get('check_publisher_journal'), staticmethod):
            raise NotImplementedError(
                f'{cls.__name__} must define static check_publisher_journal().')

        cls._define_metadata_list()
        for field in cls.metadata_list:
            if field in ('normalized_publisher', 'normalized_journal'):
                continue
            if not isinstance(cls.__dict__.get(field), functools.cached_property):
                raise NotImplementedError(
                    f'{cls.__name__}.{field} must be a cached property.')

    def __init__(self, input_data, data_type='txt', parser='html.parser',
                 publishers_index=None, publisher_journals=None):
        if data_type != 'txt':
            raise NotImplementedError('Only text input is supported.')

        raw_bytes = None
        if isinstance(input_data, str):
            try:
                with open(input_data, 'rb') as input_file:
                    raw_bytes = input_file.read()
            except (OSError, TypeError):
                pass

        self._input_data, self.reading_exception = soup_utils.convert_2_soup(
            input_data, parser=parser)
        if raw_bytes is None and self._input_data is not None:
            raw_bytes = str(self._input_data).encode('utf-8')
        self.raw_sha256 = hashlib.sha256(raw_bytes or b'').hexdigest()

        parser_dir = os.path.dirname(inspect.getfile(self.__class__.__base__))
        self._publishers_index = publishers_index or _utils.load_json(
            os.path.join(parser_dir, 'publishers_index.json'))

        own_dir = os.path.dirname(inspect.getfile(self.__class__))
        publisher_code = self.__class__.__name__.split('_')[1]
        self._publisher_journals = publisher_journals or _utils.load_json(
            os.path.join(own_dir, f'{publisher_code}_journals.json'))

    @functools.cached_property
    def normalized_publisher(self):
        return normalize_known(self.publisher, self._publishers_index)

    @functools.cached_property
    def normalized_journal(self):
        return normalize_known(self.journal, self._publisher_journals)

    @functools.cached_property
    def metadata(self):
        return {field: getattr(self, field) for field in self.metadata_list}

    @functools.cached_property
    def invalid_fields(self):
        return validate_metadata(self.metadata)[0]

    @functools.cached_property
    def warnings(self):
        return validate_metadata(self.metadata)[1]

    @property
    def success(self):
        return not self.invalid_fields

    @functools.cached_property
    def provenance(self):
        return {
            'raw_sha256': self.raw_sha256,
            'parser': self.__class__.__name__,
            'package_version': __version__,
            'git_revision': self._git_revision(),
            'parsed_at': datetime.datetime.now(datetime.UTC).isoformat(),
            'invalid_fields': self.invalid_fields,
            'warnings': self.warnings,
        }

    @staticmethod
    def _git_revision():
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', 'HEAD'],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() or None

    def to_json(self):
        return json.dumps({
            'metadata': self.metadata,
            'success': self.success,
            'provenance': self.provenance,
        }, ensure_ascii=False, sort_keys=True)
