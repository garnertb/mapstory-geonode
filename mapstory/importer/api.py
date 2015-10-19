from tastypie import fields
from tastypie.resources import ModelResource
from .models import UploadedData


class UploadedDataResource(ModelResource):
    """
    API for accessing UploadedData.
    """

    class Meta:
        queryset = UploadedData.objects.all()
        resource_name = 'data'
        allowed_methods = ['get']

    def get_object_list(self, request):
        """
        Filters the list view by the current user.
        """
        return super(UploadedDataResource, self).get_object_list(request).filter(user=request.user.id)