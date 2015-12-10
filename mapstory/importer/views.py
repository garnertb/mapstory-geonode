import json
from django.views.generic import FormView, ListView, DetailView, View, DeleteView, TemplateView
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse

from .forms import UploadFileForm
from .models import UploadedData, UploadLayer, DEFAULT_LAYER_CONFIGURATION
from .utils import GDALImport, GDALInspector, configure_time, OGRFieldConverter
from geoserver.catalog import Catalog
from geonode.geoserver.helpers import gs_catalog, ogc_server_settings
from geonode.geoserver.helpers import gs_slurp
from geonode.layers.models import Layer
from django import db
from geoserver.catalog import FailedRequestError
from .tasks import import_object


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

    def post(self, *args, **kwargs):
        configuration_options = self.request.POST.getlist('configurationOptions')

        if 'application/json' in self.request.META['CONTENT_TYPE']:
            configuration_options = json.loads(self.request.body)

        obj = self.get_object()
        obj.configuration_options = configuration_options
        obj.save()

        uploaded_file = obj.upload.uploadfile_set.first()
        import_result = import_object.delay(uploaded_file.id, configuration_options=configuration_options)

        # query the db again for this object since it may have been updated during the import
        obj = self.get_object()
        obj.task_id = import_result.id
        obj.save()

        return HttpResponse(content=json.dumps(dict(id=import_result.id, status=import_result.status)),
                            content_type='application/json')


class FileAddView(FormView, ImportHelper):
    form_class = UploadFileForm
    success_url = reverse_lazy('uploads-list')
    template_name = 'importer/new.html'

    def create_upload_session(self, upload_file):
        """
        Creates an upload session from the file.
        """
        upload = UploadedData.objects.create(user=self.request.user, state='UPLOADED', complete=True)
        upload_file.upload = upload
        upload_file.save()
        upload.size = upload_file.file.size
        upload.name = upload_file.name
        upload.save()

        description = self.get_fields(upload_file.file.path)

        for layer in description:
            configuration_options = DEFAULT_LAYER_CONFIGURATION.copy()
            configuration_options.update({'index': layer.get('index')})
            upload.uploadlayer_set.add(UploadLayer(name=layer.get('name'),
                                                   fields=layer.get('fields', {}),
                                                   index=layer.get('index'),
                                                   configuration_options=configuration_options))

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