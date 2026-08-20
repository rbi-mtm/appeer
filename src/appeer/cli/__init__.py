"""Automatically define the ``appeer <command>`` CLI

The modules in this directory must be named cmd_<command>.py
    and include a function named <command>_cli()

"""

import importlib
import pkgutil
import click


class FriendlyGroup(click.Group):
    """Turn known initialization failures into concise CLI guidance."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except RuntimeError as exc:
            if 'appeer is not initialized' in str(exc):
                raise click.ClickException(str(exc)) from exc
            raise


@click.group(name='appeer', cls=FriendlyGroup)
def appeer_cli():
    """
    Entry point for the ``appeer`` command

    """

for module_info in pkgutil.iter_modules(__path__):

    module_name = module_info.name

    if module_name.startswith('cmd'):

        cmd_name = module_name.split('_')[1]
        cmd_cli = f'{cmd_name}_cli'

        module = importlib.import_module(f'{__name__}.{module_name}')
        command = getattr(module, cmd_cli)

        appeer_cli.add_command(command, name=cmd_name)
