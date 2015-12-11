import json
from tastypie.fields import IntegerField, DictField, ListField, CharField, ToManyField
from tastypie.constants import ALL
from tastypie.resources import ModelResource
from .models import UploadedData, UploadLayer
from tastypie.authentication import SessionAuthentication
from tastypie.authorization import DjangoAuthorization,Authorization
from tastypie.utils import trailing_slash
from django.conf.urls import url
from tastypie.bundle import Bundle
from .tasks import import_object


class UploadedLayerResource(ModelResource):
    """
    API for accessing UploadedData.
    """

    geonode_layer = DictField(attribute='layer_data', readonly=True, null=True)
    configuration_options = DictField(attribute='configuration_options', null=True)
    fields = ListField(attribute='fields')
    status = CharField(attribute='status', readonly=True, null=True)

    class Meta:
        queryset = UploadLayer.objects.all()
        resource_name = 'data-layers'
        allowed_methods = ['get']
        filtering = {'id': ALL}
        authentication = SessionAuthentication()

    def get_object_list(self, request):
        """
        Filters the list view by the current user.
        """
        return super(UploadedLayerResource, self).get_object_list(request).filter(upload__user=request.user.id)

    def import_layer(self, request, **kwargs):
        """
        Imports a layer
        """

        b = Bundle()
        b.request = request
        obj = self.obj_get(b, pk=kwargs.get('pk'))
        configuration_options = request.POST.get('configurationOptions')

        if 'application/json' in request.META['CONTENT_TYPE']:
            configuration_options = json.loads(request.body)

        if isinstance(configuration_options, dict):
            obj.configuration_options = configuration_options
            obj.save()

        uploaded_file = obj.upload.uploadfile_set.first()
        import_result = import_object.delay(uploaded_file.id, configuration_options=configuration_options)

        # query the db again for this object since it may have been updated during the import
        obj = self.obj_get(b, pk=kwargs.get('pk'))
        obj.task_id = import_result.id
        obj.save()

        return self.create_response(request, {'task': obj.task_id})

    def prepend_urls(self):
        return [url(r"^(?P<resource_name>{0})/(?P<pk>\w[\w/-]*)/configure{1}$".format(self._meta.resource_name,
                                                                                     trailing_slash()),
                self.wrap_view('import_layer'), name="importer_configure"),
                ]


class UserOwnsObjectAuthorization(Authorization):

    # Optional but useful for advanced limiting, such as per user.
    def apply_limits(self, request, object_list):

        if request and hasattr(request, 'user'):
            if request.user.is_superuser:
                return object_list

            return object_list.filter(user=request.user)

        return object_list.none()


class UploadedDataResource(ModelResource):
    """
    API for accessing UploadedData.
    """

    file_size = CharField(attribute='filesize', readonly=True)
    layers = ToManyField(UploadedLayerResource, 'uploadlayer_set', full=True)
    file_url = CharField(attribute='file_url', readonly=True, null=True)

    class Meta:
        queryset = UploadedData.objects.all()
        resource_name = 'data'
        allowed_methods = ['get', 'delete']
        authorization = UserOwnsObjectAuthorization()
        authentication = SessionAuthentication()

    def get_object_list(self, request):
        """
        Filters the list view by the current user.
        """
        queryset = super(UploadedDataResource, self).get_object_list(request)

        if not request.user.is_superuser:
            return queryset.filter(user=request.user)

        return queryset
