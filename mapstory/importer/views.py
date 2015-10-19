import json
from django.views.generic import FormView, ListView, DetailView, View, DeleteView
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse

from .forms import UploadFileForm
from .models import UploadedData, UploadLayer
from .utils import GDALImport, GDALInspector, configure_time, OGRFieldConverter
from geoserver.catalog import Catalog
from geonode.geoserver.helpers import gs_catalog, ogc_server_settings
from geonode.geoserver.helpers import gs_slurp
from geonode.layers.models import Layer
from django import db
from geoserver.catalog import FailedRequestError


class UploadListView(ListView):
    model = UploadedData
    template_name = 'importer/uploads-list.html'
    queryset = UploadedData.objects.all()


class ImportHelper(object):
    """
    Import Helpers
    """

    opener = GDALInspector

    def get_fields(self, path):
        """
        Returns a list of field names and types.
        """

        with self.opener(path) as opened_file:
            return opened_file.describe_fields()


class ConfigureImport(DetailView, ImportHelper):
    model = UploadLayer
    template_name = 'importer/configure.html'
    cat = gs_catalog
    workspace = 'geonode'

    def get_or_create_datastore(self):
        connection = db.connections['datastore']
        settings = connection.settings_dict

        try:
            return self.cat.get_store(settings['NAME'])
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

            store = self.cat.create_datastore(settings['NAME'], workspace=self.workspace)
            store.connection_parameters.update(params)
            self.cat.save(store)

        return self.cat.get_store(settings['NAME'])

    def enable_time(self, layer, **options):
        """
        Configures time on the object.
        """
        lyr = self.cat.get_layer(layer)
        configure_time(lyr.resource, attribute=options.get('start_date'),
                       end_attribute=options.get('end_date'))

    def convert_field_to_time(self, layer, field):
        d = db.connections['datastore'].settings_dict
        connection_string = "PG:dbname='%s' user='%s' password='%s'" % (d['NAME'], d['USER'], d['PASSWORD'])
        with OGRFieldConverter(connection_string) as datasource:
            return datasource.convert_field(layer, field)

    def publish_layer_in_geoserver(self, layer):
        """
        Publishes a layer in geoserver.
        """
        return self.cat.publish_featuretype(layer, self.store, 'EPSG:4326')

    def publish_layer_in_geonode(self, layer):
        """
        Adds a layer in GeoNode, after it has been added to Geoserver.
        """
        return gs_slurp(workspace='geonode', store=self.store.name, filter=layer)

    def post(self, *args, **kwargs):
        self.store = self.get_or_create_datastore()

        configuration_options = self.request.POST.getlist('configurationOptions')

        if 'application/json' in self.request.META['CONTENT_TYPE']:
            configuration_options = json.loads(self.request.body)

        obj = self.get_object()
        obj.configuration_options = configuration_options
        obj.save()

        f = obj.upload.uploadfile_set.first()
        gi = GDALImport(f.file.path)
        layers = gi.import_file(configuration_options=configuration_options)

        for layer, layer_config in layers:

            for field_to_convert in layer_config.get('convert_to_date', []):
                new_field = self.convert_field_to_time(layer, field_to_convert)

                # if the start_date or end_date needed to be converted to a date
                # field, use the newly created field name
                for date_option in ('start_date', 'end_date'):
                    if layer_config.get(date_option) == field_to_convert:
                        layer_config[date_option] = new_field.lower()

            self.publish_layer_in_geoserver(layer)

            if layer_config.get('configureTime'):
                self.enable_time(layer, **layer_config)

            self.publish_layer_in_geonode(layer)

        l = Layer.objects.get(name=layer)
        obj.layer = l
        obj.save()

        return HttpResponse(content=json.dumps(dict(redirect=l.get_absolute_url())),
                            content_type='application/json')


class FileAddView(FormView, ImportHelper):
    form_class = UploadFileForm
    success_url = reverse_lazy('uploads-list')
    template_name = 'importer/new.html'

    def create_upload_session(self, upload_file):
        """
        Creates an upload session from the file.
        """
        upload = UploadedData.objects.create(user=self.request.user, state='Uploaded', complete=True)
        upload_file.upload = upload
        upload_file.save()
        upload.size = upload.size = upload_file.file.size
        upload.save()

        description = self.get_fields(upload_file.file.path)

        for layer in description:
            upload.uploadlayer_set.add(UploadLayer(name=layer.get('name'),
                                                   fields=layer.get('fields', {}),
                                                   index=layer.get('index')))

        upload.save()

    def form_valid(self, form):
        form.save(commit=True)
        self.create_upload_session(form.instance)
        return super(FileAddView, self).form_valid(form)


class UploadDescribeFields(DetailView):
    model = UploadedData

    def get(self, request, *args, **kwargs):
        layers = []

        for uploadedlayer in self.get_object().uploadlayer_set.all():
            layers.append(uploadedlayer.description)

        return HttpResponse(content=json.dumps(layers),
                            content_type='application/json')


class UploadDeleteView(DeleteView):
    model = UploadedData
    template_name = 'importer/upload_confirm_delete.html'
    success_url = reverse_lazy('uploads-list')