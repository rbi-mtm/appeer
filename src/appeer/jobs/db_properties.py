"""Descriptor mechanism to get/set values in the database through attributes"""

class JobProperty:
    """
    Get/set a value in the database through job attributes

    """

    def __init__(self, name):

        self.name = name

    def __get__(self, instance, owner):

        if instance._job_exists:
            _value = getattr(instance._job_entry, self.name)

        else:
            _value = None

        return _value

    def __set__(self, instance, val):

        if instance._job_mode == 'read':
            raise PermissionError(f'Cannot modify the {self.name} attribute in job_mode="read".')

        if instance._job_mode == 'write':

            if instance._job_exists:

                match instance._job_type:

                    case 'scrape_job':
                        instance._db.scrape_jobs.update_entry(
                                label=instance.label,
                                column_name=self.name,
                                new_value=val)

                    case 'parse_job':
                        instance._db.parse_jobs.update_entry(
                                label=instance.label,
                                column_name=self.name,
                                new_value=val)

                    case 'commit_job':

                        instance._db.commit_jobs.update_entry(
                                label=instance.label,
                                column_name=self.name,
                                new_value=val)

            else:
                raise PermissionError(f'Cannot modify "{self.name}"; the job with the label "{instance.label}" does not exist.')

class ActionProperty:
    """
    Get/set a value in the database through Action attributes

    """

    def __init__(self, name):

        self.name = name

    def __get__(self, instance, owner):

        if instance._action_exists:
            _value = getattr(instance._action_entry, self.name)

        else:
            _value = None

        return _value

    def __set__(self, instance, val):

        if instance._action_mode == 'read':
            raise PermissionError(f'Cannot modify the {self.name} attribute in action_mode="read".')

        if instance._action_mode == 'write':

            if instance._action_exists:

                match instance._action_type:

                    case 'scrape':
                        instance._db.scrapes.update_entry(
                                label=instance.label,
                                action_index=instance.action_index,
                                column_name=self.name,
                                new_value=val)

                    case 'parse':
                        instance._db.parses.update_entry(
                                label=instance.label,
                                action_index=instance.action_index,
                                column_name=self.name,
                                new_value=val)

                    case 'commit':

                        instance._db.commits.update_entry(
                                label=instance.label,
                                action_index=instance.action_index,
                                column_name=self.name,
                                new_value=val)

            else:
                raise PermissionError(f'Cannot modify "{self.name}"; the job with the label "{instance.label}" and index={instance.index} does not exist.')
