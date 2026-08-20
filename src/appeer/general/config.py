"""Creates, deletes, reads and edits the ``appeer`` configuration file"""

import sys
import os
import configparser
import click
import platformdirs

from appeer.general import log
from appeer.general import utils


class Config:
    """
    Class which handles creation, deletion, reading and editing of the
        ``appeer`` config file, which is found at
        ``platformdirs.user_config_dir(appname='appeer')/appeer.cfg``

    """

    def __init__(self):
        """
        Check for the existence of the config file
        
        If the config file exists, read its contents

        """

        self._dashes = log.get_log_dashes()

        self._config = configparser.ConfigParser()

        self._config_dir = platformdirs.user_config_dir(appname='appeer')
        self._config_path = os.path.join(self._config_dir, 'appeer.cfg')

        if self._config_exists:
            self._read_config()

    @property
    def _config_exists(self):
        """
        Checks for the existence of a file at self._config_path

        Returns
        -------
        _config_exists : bool
            True if a file exists at self._config_path, False otherwise

        """

        exists = utils.file_exists(self._config_path)

        return exists

    @_config_exists.setter
    def _config_exists(self, value):
        """
        This attribute should never be set directly

        """

        raise PermissionError('The "_config_exists" attribute cannot be directly set')

    @property
    def settings(self):
        """
        Reads the config file and stores the settings 
            to the ``self.settings`` dictionary

        """

        if self._config_exists:

            self._read_config()

            _settings = {s:dict(self._config.items(s))
                             for s in self._config.sections()}

        else:
            _settings = None

        return _settings

    @settings.setter
    def settings(self, value):
        """
        This attribute should never be set directly

        """

        raise PermissionError('The "settings" attribute cannot be directly set')

    def _define_default_values(self):
        """
        Defines the default values for the ``appeer`` config file

        """

        default_base = platformdirs.user_data_dir(appname='appeer')

        self._config['GlobalSettings'] = {'data_directory': default_base}

        self._config['ScrapeDefaults'] = {
                'sleep_time': 1.0,
                'max_tries': 3,
                'retry_sleep_time': 10.0,
                '429_sleep_time': 5.0,
                'timeout': 30.0,
                'user_agent': 'appeer/0.0.1 (scientific metadata client; contact: juraj.ovcar@gmail.com)'
                }

    def create_config_file(self):
        """
        Creates the ``appeer`` config file. If ``self._config_path``
        already exists, the user is prompted if they want to proceed
        with the current config file

        """

        if self._config_exists:

            click.echo(f'WARNING: appeer config file already exists at {self._config_path}')
            click.echo(self._dashes)
            self._handle_config_exists()

        else:

            self._define_default_values()

            if not utils.directory_exists(self._config_dir):
                os.makedirs(self._config_dir)

            try:
                with open(self._config_path, 'w+',
                        encoding='utf-8') as configfile:
                    self._config.write(configfile)

            except PermissionError:
                click.echo('Failed to initialize the appeer config file at {self._config_path}. Exiting.')
                sys.exit()

            if self._config_exists:

                click.echo(f'Path to the appeer configuration file: {self._config_path}')
                click.echo(self._dashes)
                self._read_config()

            else:
                click.echo('Failed to initialize the appeer config file at {self._config_path}. Exiting.')
                sys.exit()

            default_base = self.settings['GlobalSettings']['data_directory']

            click.echo('appeer will store all data in a given base directory.')
            click.echo(f'The default directory is: {default_base}\n')

            new_path = input('Press "Enter" to keep the default or provide another path:\n')

            if len(new_path) > 0:

                self.edit_config_file(
                        update_dict={
                            'GlobalSettings': {'data_directory': new_path}
                            }
                        )

            click.echo(self._dashes)
            click.echo('appeer config successful!')
            click.echo(self._dashes)

            self.print_config()

    def _handle_config_exists(self):
        """
        Handles the case when the user tries to run ``appeer init``
        with a preexisting config file

        """

        self.print_config()

        proceed = log.ask_yes_no('Do you want to proceed with the current config file? [Y/n]\n')

        if proceed == 'Y':

            click.echo('Proceeding with the current appeer config file.')
            click.echo(self._dashes)

        elif proceed == 'n':

            click.echo('Stopping, as requested.')
            click.echo('Check "appeer config --help" for instructions on editing the config file or run "appeer clean config" to delete the config file.')
            click.echo(self._dashes)

            sys.exit()

    def _read_config(self):
        """
        Reads the contents of the config file and
        stores the values to ``self.{section_name}``

        """

        if self._config_exists:

            self._config.read(self._config_path)

        else:

            click.echo('The appeer config file does not exist.')

    def print_config(self):
        """
        Prints the contents of the config file

        """

        if self._config_exists:

            with open(self._config_path, 'r', encoding='utf-8') as f:

                click.echo(f'Contents of the appeer config file at {self._config_path}:')
                click.echo(self._dashes)
                click.echo(f.read(), nl=False)

                click.echo(self._dashes)

        else:
            click.echo('The appeer config file does not exist.')

    def edit_config_file(self, update_dict):
        """
        Edit the contents of the config file

        The update_dict should be of form:

        {
        section0: {subsection00: value00, subsection01: value01},
        section1: {subsection10: value10, subsection11: value11},
        ...},

        where the sections and subsections correspond to the configuration file

        Parameters
        ----------
        update_dict : dict
            Dictionary of form
            {section0: {subsection00: value00, subsection01: value01},
            section1: {subsection10: value10, subsection12: value12},
            ...}

        """

        self._read_config()

        all_sections = self._config.sections()

        for section, subsections_values in update_dict.items():

            if section not in all_sections:
                click.echo(f'Invalid configuration section {section}')

            else:

                all_subsections = self._config[section].keys()

                for subsection, value in subsections_values.items():

                    if subsection not in all_subsections:
                        click.echo(f'Invalid configuration subsection {subsection}')

                    else:

                        self._config[section][subsection] = value

                        with open(self._config_path, 'w',
                                encoding='utf-8') as configfile:

                            self._config.write(configfile)

                        click.echo(f'[{section}]: {subsection} updated to {value}')

                        self._read_config()

    def edit_config_by_subsection(self, subsection, value):
        """
        Edits the contents of the config file by passing only the
        subsection and the value, while the section is automatically found

        Parameters
        ----------
        subsection : str
            Subsection in the config file
        value : str | float | int
            Value that the subsection is updated to

        """

        self._read_config()
        all_sections = self._config.sections()

        update_dict = {}

        for section in all_sections:

            if subsection in self._config.options(section):

                update_dict[section] = {subsection: value}
                self.edit_config_file(update_dict=update_dict)

                break

        else:
            click.echo(f'Invalid config option "{subsection}"')

    def clean_config(self):
        """
        Deletes the ``self._config_dir`` configuration directory

        """

        if not utils.directory_exists(self._config_dir):
            click.echo('Nothing to delete.')

        else:
            utils.delete_directory(self._config_dir)
