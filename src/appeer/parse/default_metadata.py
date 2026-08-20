"""Default list of metadata properties parsed from a publication."""

from appeer.parse.metadata import PUBLICATION_FIELDS

def default_metadata():
    """
    Default list of metadata properties to be parsed from a publication

    This canonical list is deliberately independent from database schemas.

    Returns
    -------
    metadata_list : list of str
        Default metadata properties

    """

    return list(PUBLICATION_FIELDS)
