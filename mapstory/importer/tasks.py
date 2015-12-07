from celery.task import task
from .utils import GDALImport

@task
def import_object(f, configuration_options):
    """
    Imports a file into GeoNode.
    """

    gi = GDALImport(f.file.path)
    layers = gi.handle(configuration_options=configuration_options)
    return layers