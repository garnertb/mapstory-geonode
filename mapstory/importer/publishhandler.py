from django.utils.module_loading import import_by_path
from geonode.geoserver.helpers import gs_catalog
from django import db
from geoserver.catalog import FailedRequestError
from geonode.geoserver.helpers import gs_slurp

class PublishHandler(object):

    def __init__(self, *args, **kwargs):
        pass

    def publish(self, layername, *args, **kwargs):
        raise NotImplementedError('Subclass should implement this.')


class GeoserverPublishHandler(PublishHandler):
    catalog = gs_catalog
    workspace = 'geonode'

    def get_or_create_datastore(self):
        connection = db.connections['datastore']
        settings = connection.settings_dict

        try:
            return self.catalog.get_store(settings['NAME'])
        except FailedRequestError:

            params = {'database': settings['NAME'],
                      'passwd': settings['PASSWORD'],
                      'namespace': 'http://www.geonode.org/',
                      'type': 'PostGIS',
                      'dbtype': 'postgis',
                      'host': settings['HOST'],
                      'user': settings['USER'],
                      'port': settings['PORT'],
                      'enabled': "True"}

            store = self.catalog.create_datastore(settings['NAME'], workspace=self.workspace)
            store.connection_parameters.update(params)
            self.catalog.save(store)

        return self.catalog.get_store(settings['NAME'])

    @property
    def store(self):
        return self.get_or_create_datastore()

    def publish(self, layername, *args, **kwargs):
        self.catalog.publish_featuretype(layername, self.store, 'EPSG:4326')


class GeonNodePublishHandler(PublishHandler):
    workspace = 'geonode'

    def publish(self, layername, *args, **kwargs):
        return gs_slurp(workspace='geonode', filter=layername)


def load_handler(path, *args, **kwargs):
    """
    Given a path to a handler, return an instance of that handler.
    E.g.::
        >>> from django.http import HttpRequest
        >>> request = HttpRequest()
        >>> load_handler('django.core.files.uploadhandler.TemporaryFileUploadHandler', request)
        <TemporaryFileUploadHandler object at 0x...>
    """
    return import_by_path(path)(*args, **kwargs)